import sqlite3
from pathlib import Path
from typing import Any

from backend.tool_registry import Tool, ToolRegistry, error


def register_calculation(registry: ToolRegistry, database: Path) -> None:
    def calculate(limits: list[dict[str, Any]]) -> dict[str, Any]:
        results = []
        names: set[str] = set()
        for limit in limits:
            if not limit["name"] or limit["name"] in names:
                return error("INVALID_ARGUMENT", "限制名稱不可空白或重複")
            names.add(limit["name"])
            if any(type(limit[field]) is not int for field in ("maximum", "used")):
                return error("INVALID_ARGUMENT", "次數必須為整數")
            if limit["source"] == "help_article":
                if not limit["article_id"]:
                    return error("INVALID_ARGUMENT", "政策文章識別碼不可空白")
                with sqlite3.connect(database) as conn:
                    policy = conn.execute("SELECT request_limit, limit_window FROM help_articles WHERE article_id = ?", (limit["article_id"],)).fetchone()
                if policy is None:
                    return error("NOT_FOUND", "查無政策文章")
                if policy != (limit["maximum"], limit["window"]):
                    return error("INVALID_ARGUMENT", "政策上限或統計期間不一致，或文章不提供請求額度")
            remaining = max(limit["maximum"] - limit["used"], 0)
            results.append({**limit, "remaining": remaining, "over_limit": limit["used"] > limit["maximum"]})
        return {"ok": True, "data": {"limits": results, "sendable_now": min(item["remaining"] for item in results), "unit": "requests", "simulated": True}}

    registry.register(Tool("calculate_remaining_requests", "由 Python 試算剩餘請求次數。每項必須有明確期間、上限與使用者提供的同期間用量；缺資料先詢問，不猜真實用量。政策來源須先查資訊。不能計算 Token、金額或並行數。", {
        "type": "object", "properties": {"limits": {"type": "array", "minItems": 1, "maxItems": 4, "items": {
            "type": "object", "properties": {
                "name": {"type": "string", "minLength": 1, "maxLength": 40},
                "window": {"type": "string", "enum": ["minute", "day"]},
                "maximum": {"type": "integer", "minimum": 0, "maximum": 1_000_000},
                "used": {"type": "integer", "minimum": 0, "maximum": 1_000_000},
                "source": {"type": "string", "enum": ["user_assumption", "help_article"]},
                "article_id": {"type": "string", "minLength": 1},
            }, "required": ["name", "window", "maximum", "used", "source"], "additionalProperties": False,
            "if": {"properties": {"source": {"const": "help_article"}}},
            "then": {"required": ["article_id"]}, "else": {"not": {"required": ["article_id"]}},
        }}}, "required": ["limits"], "additionalProperties": False,
    }, calculate, "計算"))

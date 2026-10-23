import sqlite3
from pathlib import Path
from typing import Any

from backend.tool_registry import Tool, ToolRegistry, error


def register_human_support(registry: ToolRegistry, database: Path) -> None:
    def support(reason: str) -> dict[str, Any]:
        with sqlite3.connect(database) as conn:
            row = conn.execute("SELECT content FROM help_articles WHERE article_id = ?", ("H08",)).fetchone()
        if row is None:
            return error("NOT_FOUND", "查無人工支援指引")
        return {"ok": True, "data": {
            "article_id": "H08", "instructions": row[0],
            "channel_configured": False, "handoff_completed": False, "simulated": True,
        }}

    registry.register(Tool("get_human_support", "使用者要求人工協助、持續登入失敗或工具資料不足需要維運時，取得 H08 模擬人工支援指引。管道尚未配置；不建立工單、不傳送訊息、不代表真人已接手。不收帳密、API Key、電子郵件或自由文字。", {
        "type": "object", "properties": {
            "reason": {"type": "string", "enum": ["login", "permission", "api", "outage", "other"]},
        }, "required": ["reason"], "additionalProperties": False,
    }, support, "轉真人"))

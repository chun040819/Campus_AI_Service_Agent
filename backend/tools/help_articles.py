import sqlite3
from pathlib import Path
from typing import Any

from backend.tool_registry import Tool, ToolRegistry, error


def create_registry(database: Path) -> ToolRegistry:
    def search(query: str, audience: str = "all", limit: int = 5) -> dict[str, Any]:
        with sqlite3.connect(database) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM help_articles WHERE (instr(lower(topic), lower(?)) > 0 OR instr(lower(keywords), lower(?)) > 0 OR instr(lower(content), lower(?)) > 0) AND (? = 'all' OR audience IN (?, 'all')) ORDER BY article_id LIMIT ?",
                (query, query, query, audience, audience, limit),
            ).fetchall()
        if not rows:
            return error("NOT_FOUND", "查無符合資料；可換具體關鍵字重查")
        return {"ok": True, "data": {"articles": [dict(row) for row in rows], "simulated": True}}

    registry = ToolRegistry()
    registry.register(Tool("search_help_articles", "查詢虛構校園平台操作與政策。以具體主題詞做字面子字串搜尋；不查故障進度、不計算剩餘次數。查無時可換詞重查，不可補造政策。", {
        "type": "object", "properties": {
            "query": {"type": "string", "minLength": 1, "maxLength": 100},
            "audience": {"type": "string", "enum": ["student", "teacher", "all"], "default": "all"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 8, "default": 5},
        }, "required": ["query"], "additionalProperties": False,
    }, search, "查資訊"))
    return registry

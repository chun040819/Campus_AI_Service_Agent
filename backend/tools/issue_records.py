import sqlite3
from pathlib import Path
from typing import Any

from backend.tool_registry import Tool, ToolRegistry, error


def register_records(registry: ToolRegistry, database: Path) -> None:
    def search(query: str | None = None, issue_id: str | None = None, status: str | None = None, limit: int = 5) -> dict[str, Any]:
        with sqlite3.connect(database) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM issue_records WHERE (? IS NULL OR instr(lower(title), lower(?)) > 0 OR instr(lower(service), lower(?)) > 0 OR instr(lower(symptom), lower(?)) > 0 OR instr(lower(workaround), lower(?)) > 0) AND (? IS NULL OR issue_id = ?) AND (? IS NULL OR status = ?) ORDER BY julianday(updated_at) DESC, issue_id ASC LIMIT ?",
                (query, query, query, query, query, issue_id, issue_id, status, status, limit),
            ).fetchall()
        if not rows:
            return error("NOT_FOUND", "查無符合的公開模擬故障紀錄")
        records = [dict(row) for row in rows]
        for record in records:
            record["available"] = bool(record["available"])
        return {"ok": True, "data": {"records": records, "simulated": True}}

    registry.register(Tool("search_issue_records", "查公開模擬平台故障紀錄與處理階段，不查私人工單。無篩選時列最近紀錄；多條件取交集。available 是最後更新時服務可用性，不由 status 推導，不代表目前真實服務狀態。affected_requests 單位為次，並非個人用量。回答須保留更新時間與模擬標示。操作指引使用 search_help_articles。", {
        "type": "object", "properties": {
            "query": {"type": "string", "minLength": 1, "maxLength": 100},
            "issue_id": {"type": "string", "pattern": "^INC-[0-9]{3}$"},
            "status": {"type": "string", "enum": ["investigating", "identified", "monitoring", "resolved"]},
            "limit": {"type": "integer", "minimum": 1, "maximum": 15, "default": 5},
        }, "additionalProperties": False,
    }, search, "查紀錄"))

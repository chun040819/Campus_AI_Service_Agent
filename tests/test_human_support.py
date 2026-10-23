from pathlib import Path
import sqlite3

import pytest

from backend.database import import_articles
from backend.tools.help_articles import create_registry


@pytest.mark.parametrize("reason", ["login", "permission", "api", "outage", "other", " login "])
def test_support_returns_seed_instructions_without_handoff(tmp_path: Path, reason: str) -> None:
    db = tmp_path / "demo.db"
    import_articles(Path("data/help_articles.csv"), db)
    registry = create_registry(db)
    result = registry.execute("get_human_support", {"reason": reason})
    assert result["ok"] is True
    data = result["data"]
    assert data["article_id"] == "H08"
    assert data["channel_configured"] is False
    assert data["handoff_completed"] is False
    assert data["simulated"] is True
    assert "錯誤碼" in data["instructions"]
    assert "發生時間" in data["instructions"]
    assert "重現步驟" in data["instructions"]
    assert data["instructions"] == next(article["content"] for article in registry.execute("search_help_articles", {"query": "人工支援"})["data"]["articles"] if article["article_id"] == "H08")


@pytest.mark.parametrize("arguments", [{}, {"reason": "invalid"}, {"reason": ""}, {"reason": None}, {"reason": True}, {"reason": "login", "email": "private@example.com"}])
def test_support_rejects_invalid_arguments(tmp_path: Path, arguments: dict) -> None:
    result = create_registry(tmp_path / "unused.db").execute("get_human_support", arguments)
    assert result["error"]["code"] == "INVALID_ARGUMENT"


def test_support_missing_article_and_storage_failure(tmp_path: Path) -> None:
    db = tmp_path / "demo.db"
    import_articles(Path("data/help_articles.csv"), db)
    registry = create_registry(db)
    with sqlite3.connect(db) as conn:
        conn.execute("DELETE FROM help_articles WHERE article_id = ?", ("H08",))
    assert registry.execute("get_human_support", {"reason": "login"})["error"]["code"] == "NOT_FOUND"
    db.unlink()
    assert registry.execute("get_human_support", {"reason": "login"}) == {"ok": False, "error": {"code": "INTERNAL_ERROR", "message": "工具暫時無法使用"}}

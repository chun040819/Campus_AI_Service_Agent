from pathlib import Path

import pytest

from backend.database import import_articles
from backend.tools.help_articles import create_registry


def test_registry_queries_real_seed_and_rejects_invalid_arguments(tmp_path: Path) -> None:
    db = tmp_path / "demo.db"
    import_articles(Path("data/help_articles.csv"), db)
    registry = create_registry(db)
    result = registry.execute("search_help_articles", {"query": " API Key "})
    assert result["ok"] is True
    assert result["data"]["articles"][0]["article_id"] == "H01"
    assert result["data"]["simulated"] is True


@pytest.mark.parametrize("arguments,code", [
    ({"query": "%"}, "NOT_FOUND"),
    ({"query": "不存在的主題"}, "NOT_FOUND"), ({"query": " "}, "INVALID_ARGUMENT"),
    ({"query": "429", "limit": 0}, "INVALID_ARGUMENT"),
    ({"query": "429", "limit": True}, "INVALID_ARGUMENT"),
    ({"query": "429", "limit": 1.0}, "INVALID_ARGUMENT"),
    ({"query": "429", "sql": "DROP TABLE help_articles"}, "INVALID_ARGUMENT"),
])
def test_invalid_and_missing_results(tmp_path: Path, arguments: dict[str, object], code: str) -> None:
    db = tmp_path / "demo.db"
    import_articles(Path("data/help_articles.csv"), db)
    registry = create_registry(db)
    underscore = registry.execute("search_help_articles", {"query": "_"})
    assert [a["article_id"] for a in underscore["data"]["articles"]] == ["H02"]
    assert registry.execute("search_help_articles", arguments)["error"]["code"] == code
    assert registry.execute("unknown", {})["error"]["code"] == "INVALID_ARGUMENT"


def test_audience_sort_limit_and_reimport(tmp_path: Path) -> None:
    db = tmp_path / "demo.db"
    for _ in range(2):
        import_articles(Path("data/help_articles.csv"), db)
    registry = create_registry(db)
    result = registry.execute("search_help_articles", {"query": "每日", "audience": "student", "limit": 8})
    ids = [article["article_id"] for article in result["data"]["articles"]]
    assert "H04" in ids and "H05" not in ids
    assert ids == sorted(set(ids))
    assert len(registry.execute("search_help_articles", {"query": "API", "limit": 1})["data"]["articles"]) == 1
    db.unlink()
    assert registry.execute("search_help_articles", {"query": "API"})["error"]["code"] == "INTERNAL_ERROR"


def test_bad_csv_reports_row_and_preserves_existing_data(tmp_path: Path) -> None:
    db = tmp_path / "demo.db"
    import_articles(Path("data/help_articles.csv"), db)
    source = tmp_path / "bad.csv"
    source.write_text(Path("data/help_articles.csv").read_text().replace("H02,", "H01,"), encoding="utf-8")
    with pytest.raises(ValueError, match="bad.csv:3"):
        import_articles(source, db)
    assert create_registry(db).execute("search_help_articles", {"query": "429"})["ok"] is True

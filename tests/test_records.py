from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import create_app
from backend.tools.help_articles import create_registry


def test_startup_imports_records_and_returns_unavailable_as_success(tmp_path: Path) -> None:
    db = tmp_path / "demo.db"
    with TestClient(create_app(database=db, api_key="", model="")):
        registry = create_registry(db)
        result = registry.execute("search_issue_records", {"issue_id": " INC-001 "})
        assert result["ok"] is True
        record = result["data"]["records"][0]
        assert record["issue_id"] == "INC-001"
        assert record["status"] == "investigating"
        assert record["available"] is False
        assert record["affected_requests"] == 12
        assert record["updated_at"] == "2026-10-20T08:00:00Z"
        assert result["data"]["simulated"] is True


def test_filter_sort_limit_and_reimport(tmp_path: Path) -> None:
    from backend.database import import_records

    db = tmp_path / "demo.db"
    for _ in range(2):
        import_records(Path("data/issue_records.csv"), db)
    registry = create_registry(db)
    records = registry.execute("search_issue_records", {"limit": 15})["data"]["records"]
    assert len(records) == 15
    assert [r["issue_id"] for r in records[:5]] == ["INC-001", "INC-002", "INC-003", "INC-004", "INC-005"]
    assert len(registry.execute("search_issue_records", {})["data"]["records"]) == 5
    result = registry.execute("search_issue_records", {"query": "429", "status": "resolved", "limit": 1})
    assert result["data"]["records"][0]["issue_id"] == "INC-004"
    assert result["data"]["records"][0]["available"] is True
    assert result["data"]["records"][0]["affected_requests"] == 30
    assert all(r["status"] == "resolved" for r in registry.execute("search_issue_records", {"status": "resolved", "limit": 15})["data"]["records"])
    assert registry.execute("search_issue_records", {"query": "API_KEYS"})["data"]["records"][0]["issue_id"] == "INC-003"


def test_invalid_missing_and_internal_errors(tmp_path: Path) -> None:
    from backend.database import import_records

    db = tmp_path / "demo.db"
    import_records(Path("data/issue_records.csv"), db)
    registry = create_registry(db)
    for args in [{"issue_id": "INC-999"}, {"query": "%"}, {"query": "不存在"}, {"issue_id": "INC-001", "status": "resolved"}]:
        assert registry.execute("search_issue_records", args)["error"]["code"] == "NOT_FOUND"
    for args in [{"query": " "}, {"query": "x" * 101}, {"issue_id": "INC-01"}, {"issue_id": "INC-001\nextra"}, {"status": "open"}, {"limit": 0}, {"limit": 16}, {"limit": True}, {"limit": 1.0}, {"query": None}, {"sql": "DROP TABLE issue_records"}]:
        assert registry.execute("search_issue_records", args)["error"]["code"] == "INVALID_ARGUMENT"
    db.unlink()
    assert registry.execute("search_issue_records", {})["error"]["code"] == "INTERNAL_ERROR"


def test_bad_import_preserves_records_and_reports_line(tmp_path: Path) -> None:
    import pytest
    from backend.database import import_records

    db = tmp_path / "demo.db"
    seed = Path("data/issue_records.csv").read_text()
    import_records(Path("data/issue_records.csv"), db)
    source = tmp_path / "bad.csv"
    for old, new in [("INC-002,", "INC-001,"), ("false,12", "unknown,12"), ("false,12", "false,-1"), ("investigating,false", "open,false"), ("2026-10-20T08:00:00Z", "2026-02-30T08:00:00Z")]:
        source.write_text(seed.replace(old, new))
        with pytest.raises(ValueError, match=r"bad.csv:[23]:"):
            import_records(source, db)
        assert len(create_registry(db).execute("search_issue_records", {"limit": 15})["data"]["records"]) == 15
    source.write_text("\n".join(seed.splitlines()[:15]) + "\n")
    with pytest.raises(ValueError, match="at least 15"):
        import_records(source, db)


def test_time_ties_and_availability_are_independent(tmp_path: Path) -> None:
    from backend.database import import_records

    source = tmp_path / "records.csv"
    seed = Path("data/issue_records.csv").read_text()
    source.write_text(seed.replace("2026-10-20T07:00:00Z", "2026-10-20T08:00:00+00:00").replace("investigating,false,12", "investigating,true,12"))
    db = tmp_path / "demo.db"
    import_records(source, db)
    records = create_registry(db).execute("search_issue_records", {"limit": 2})["data"]["records"]
    assert [r["issue_id"] for r in records] == ["INC-001", "INC-002"]
    assert records[0]["available"] is True
    assert records[0]["status"] == "investigating"


def test_latest_record_respects_microseconds(tmp_path: Path) -> None:
    from backend.database import import_records

    source = tmp_path / "records.csv"
    source.write_text(Path("data/issue_records.csv").read_text().replace("2026-10-20T08:00:00Z", "2026-10-20T08:00:00.000001Z").replace("2026-10-20T07:00:00Z", "2026-10-20T08:00:00.000002Z"))
    db = tmp_path / "demo.db"
    import_records(source, db)
    result = create_registry(db).execute("search_issue_records", {"limit": 1})
    assert result["data"]["records"][0]["issue_id"] == "INC-002"

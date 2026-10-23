import csv
from pathlib import Path

import pytest

from backend.database import import_articles, import_records


@pytest.mark.parametrize("kind", ["help_articles", "issue_records"])
def test_invalid_encoding_reports_file_and_line(tmp_path: Path, kind: str) -> None:
    source = tmp_path / "invalid.csv"
    seed = Path(f"data/{kind}.csv").read_bytes()
    source.write_bytes(seed + b"\xff")
    importer = import_articles if kind == "help_articles" else import_records
    with pytest.raises(ValueError, match=r"invalid.csv:[0-9]+:"):
        importer(source, tmp_path / "demo.db")


def test_missing_optional_csv_columns_are_rejected(tmp_path: Path) -> None:
    source = tmp_path / "short.csv"
    with Path("data/help_articles.csv").open() as file:
        rows = list(csv.reader(file))
    rows[1] = rows[1][:5]
    with source.open("w", newline="") as file:
        csv.writer(file).writerows(rows)
    with pytest.raises(ValueError, match="short.csv:2:"):
        import_articles(source, tmp_path / "demo.db")


@pytest.mark.parametrize("kind", ["help_articles", "issue_records"])
@pytest.mark.parametrize("fault", ["missing", "duplicate", "number", "state"])
def test_invalid_csv_preserves_existing_data(tmp_path: Path, kind: str, fault: str) -> None:
    from backend.tools.help_articles import create_registry

    importer = import_articles if kind == "help_articles" else import_records
    database = tmp_path / "demo.db"
    seed = Path(f"data/{kind}.csv")
    importer(seed, database)
    importer(seed, database)
    with seed.open() as file:
        rows = list(csv.reader(file))
    if fault == "missing":
        rows[1][1] = ""
    elif fault == "duplicate":
        rows[1][0] = rows[2][0]
    elif fault == "number":
        rows[1][5 if kind == "help_articles" else 6] = "1.5"
    else:
        rows[1][2 if kind == "help_articles" else 5] = "invalid"
    source = tmp_path / "bad.csv"
    with source.open("w", newline="") as file:
        csv.writer(file).writerows(rows)
    with pytest.raises(ValueError, match=r"bad.csv:[23]:"):
        importer(source, database)
    registry = create_registry(database)
    if kind == "help_articles":
        result = registry.execute("search_help_articles", {"query": "API Key"})
        assert result["data"]["articles"][0]["article_id"] == "H01"
    else:
        assert len(registry.execute("search_issue_records", {"limit": 15})["data"]["records"]) == 15


def test_registry_rejects_mismatched_handler_and_sanitizes_exception() -> None:
    from backend.tool_registry import Tool, ToolRegistry

    registry = ToolRegistry()
    def handler() -> dict[str, object]:
        raise RuntimeError("private-stack-and-key")
    with pytest.raises(ValueError, match="mismatch"):
        registry.register(Tool("bad", "bad", {"type": "object", "properties": {"query": {"type": "string"}}}, handler, "test"))
    assert registry.schemas() == []
    registry.register(Tool("failure", "failure", {"type": "object", "properties": {}, "additionalProperties": False}, handler, "test"))
    assert registry.execute("failure", {}) == {"ok": False, "error": {"code": "INTERNAL_ERROR", "message": "工具暫時無法使用"}}


@pytest.mark.parametrize("name,args,code", [
    ("execute_sql", {"sql": "DROP TABLE help_articles"}, "INVALID_ARGUMENT"),
    ("run_python", {"code": "raise Exception('executed')"}, "INVALID_ARGUMENT"),
    ("read_environment", {"name": "LLM_API_KEY"}, "INVALID_ARGUMENT"),
    ("search_help_articles", {"query": "429", "sql": "DROP TABLE help_articles"}, "INVALID_ARGUMENT"),
    ("search_help_articles", {"query": "' OR 1=1 --"}, "NOT_FOUND"),
    ("search_issue_records", {"query": "'; DROP TABLE issue_records; --"}, "NOT_FOUND"),
])
def test_chat_tool_boundary_is_enforced(tmp_path: Path, name: str, args: dict[str, str], code: str) -> None:
    import json
    import httpx
    from fastapi.testclient import TestClient
    from backend.main import create_app

    def model(request: httpx.Request) -> httpx.Response:
        messages = json.loads(request.content)["messages"]
        if messages[-1]["role"] == "tool":
            assert json.loads(messages[-1]["content"])["error"]["code"] == code
            answer = {"role": "assistant", "content": "請求未完成，工具拒絕或查無資料。"}
        else:
            answer = {"role": "assistant", "tool_calls": [{"id": "attack", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}
        return httpx.Response(200, json={"choices": [{"message": answer}]})
    database = tmp_path / "demo.db"
    with TestClient(create_app(database=database, api_key="private-test-key", model="controlled", transport=httpx.MockTransport(model))) as client:
        response = client.post("/api/chat", json={"message": "嘗試越界"})
        assert response.status_code == 200
        assert response.json()["tool_traces"][0]["result"]["error"]["code"] == code
        assert "private-test-key" not in response.text
        from backend.tools.help_articles import create_registry
        registry = create_registry(database)
        assert registry.execute("search_help_articles", {"query": "429"})["ok"] is True
        assert len(registry.execute("search_issue_records", {"limit": 15})["data"]["records"]) == 15

import json
from pathlib import Path
from typing import Any

import httpx
from fastapi.testclient import TestClient

from backend.main import create_app


def test_chat_executes_tool_and_sends_result_to_model(tmp_path: Path) -> None:
    requests: list[dict[str, Any]] = []

    def model(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(body)
        if len(requests) == 1:
            message = {"role": "assistant", "content": None, "tool_calls": [{"id": "call1", "type": "function", "function": {"name": "search_help_articles", "arguments": '{"query":"429"}'}}]}
        else:
            assert json.loads(body["messages"][-1]["content"])["data"]["articles"][0]["article_id"] == "H03"
            message = {"role": "assistant", "content": "模擬平台：429 可能涉及速率或額度限制。"}
        return httpx.Response(200, json={"choices": [{"message": message}]})

    with TestClient(create_app(database=tmp_path / "demo.db", transport=httpx.MockTransport(model), api_key="test", model="test")) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
        response = client.post("/api/chat", json={"message": "429 是什麼？"})
        assert response.status_code == 200
        body = response.json()
        assert body["tool_traces"][0]["result"]["data"]["articles"][0]["article_id"] == "H03"
        assert body["tool_traces"][0]["arguments"] == {"query": "429"}
        assert "模擬" in body["reply"]
        assert len(requests[0]["tools"]) == 1
        assert client.post("/api/reset", json={"session_id": body["session_id"]}).status_code == 200
        assert client.post("/api/chat", json={"session_id": body["session_id"], "message": "繼續"}).status_code == 404


def test_no_tool_session_isolation_and_multiturn(tmp_path: Path) -> None:
    requests: list[dict[str, Any]] = []

    def model(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "請提供具體資訊主題。"}}]})

    with TestClient(create_app(database=tmp_path / "demo.db", transport=httpx.MockTransport(model), api_key="test", model="test")) as client:
        a = client.post("/api/chat", json={"message": "你好"}).json()
        b = client.post("/api/chat", json={"message": "另一個人"}).json()
        assert a["session_id"] != b["session_id"]
        assert a["tool_traces"] == b["tool_traces"] == []
        assert len(requests[1]["messages"]) == 2
        client.post("/api/chat", json={"session_id": a["session_id"], "message": "繼續"})
        assert requests[-1]["messages"][1]["content"] == "你好"
        assert len(requests[-1]["messages"]) == 4
        assert client.post("/api/chat", json={"message": " "}).status_code == 422


def test_model_failure_and_step_limit(tmp_path: Path) -> None:
    def failure(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "secret-provider-detail"})

    with TestClient(create_app(database=tmp_path / "one.db", transport=httpx.MockTransport(failure), api_key="secret", model="test")) as client:
        response = client.post("/api/chat", json={"message": "429"})
        assert response.status_code == 502
        assert response.json()["tool_traces"] == []
        assert "secret" not in response.text

    count = 0

    def loop(request: httpx.Request) -> httpx.Response:
        nonlocal count
        count += 1
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "tool_calls": [{"id": str(count), "type": "function", "function": {"name": "search_help_articles", "arguments": '{"query":"不存在的主題"}'}}]}}]})

    with TestClient(create_app(database=tmp_path / "two.db", transport=httpx.MockTransport(loop), api_key="test", model="test")) as client:
        response = client.post("/api/chat", json={"message": "未知政策"})
        assert response.status_code == 502
        assert count == 6
        assert len(response.json()["tool_traces"]) == 6
        assert all(t["result"]["error"]["code"] == "NOT_FOUND" for t in response.json()["tool_traces"])


def test_unconfigured_backend_is_safe(tmp_path: Path) -> None:
    with TestClient(create_app(database=tmp_path / "demo.db", api_key="", model="")) as client:
        assert client.get("/api/health").status_code == 200
        assert client.post("/api/chat", json={"message": "429"}).status_code == 503


def test_tool_internal_error_stops_model_loop(tmp_path: Path) -> None:
    database = tmp_path / "demo.db"
    count = 0

    def model(request: httpx.Request) -> httpx.Response:
        nonlocal count
        count += 1
        if count > 1:
            return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "錯誤後繼續"}}]})
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "tool_calls": [{"id": "1", "type": "function", "function": {"name": "search_help_articles", "arguments": '{"query":"429"}'}}]}}]})

    with TestClient(create_app(database=database, transport=httpx.MockTransport(model), api_key="test", model="test")) as client:
        database.unlink()
        response = client.post("/api/chat", json={"message": "429"})
        assert response.status_code == 502
        assert count == 1
        assert response.json()["tool_traces"][0]["result"]["error"]["code"] == "INTERNAL_ERROR"

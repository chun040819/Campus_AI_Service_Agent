import json
from pathlib import Path
from typing import Any

import httpx
import pytest
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
        assert {t["function"]["name"] for t in requests[0]["tools"]} == {"search_help_articles", "search_issue_records", "calculate_remaining_requests", "get_human_support"}
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


def test_record_chat_preserves_results_in_trace_and_model_context(tmp_path: Path) -> None:
    for arguments, expected in [({"issue_id": "INC-001"}, "INC-001"), ({"issue_id": "INC-999"}, "NOT_FOUND"), ({"limit": 16}, "INVALID_ARGUMENT")]:
        def model(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            if body["messages"][-1]["role"] != "tool":
                message: dict[str, Any] = {"role": "assistant", "tool_calls": [{"id": "r1", "type": "function", "function": {"name": "search_issue_records", "arguments": json.dumps(arguments)}}]}
            else:
                result = json.loads(body["messages"][-1]["content"])
                if expected == "INC-001":
                    assert result["data"]["records"][0]["available"] is False
                else:
                    assert result["error"]["code"] == expected
                message = {"role": "assistant", "content": "模擬紀錄查詢結果。"}
            return httpx.Response(200, json={"choices": [{"message": message}]})

        with TestClient(create_app(database=tmp_path / "records.db", transport=httpx.MockTransport(model), api_key="test", model="test")) as client:
            response = client.post("/api/chat", json={"message": "查公開故障"})
            assert response.status_code == 200
            trace = response.json()["tool_traces"][0]
            assert trace["arguments"] == arguments
            if expected == "INC-001":
                assert trace["result"]["data"]["records"][0]["affected_requests"] == 12
            else:
                assert trace["result"]["error"]["code"] == expected


def test_policy_calculation_chat_preserves_source_inputs_units_and_output(tmp_path: Path) -> None:
    count = 0
    limits = [
        {"name": "每日", "window": "day", "maximum": 20, "used": 8, "source": "help_article", "article_id": "H04"},
        {"name": "每分鐘", "window": "minute", "maximum": 5, "used": 4, "source": "help_article", "article_id": "H06"},
    ]

    def model(request: httpx.Request) -> httpx.Response:
        nonlocal count
        count += 1
        body = json.loads(request.content)
        if count == 1:
            name, arguments = "search_help_articles", {"query": "次", "audience": "student"}
        elif count == 2:
            articles = json.loads(body["messages"][-1]["content"])["data"]["articles"]
            assert {"H04", "H06"} <= {article["article_id"] for article in articles}
            name, arguments = "calculate_remaining_requests", {"limits": limits}
        else:
            data = json.loads(body["messages"][-1]["content"])["data"]
            assert data["sendable_now"] == 1
            assert data["unit"] == "requests"
            assert [item["remaining"] for item in data["limits"]] == [12, 1]
            return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "依模擬政策 H04/H06 與你提供的用量，當下可發送 1 次；不是實際帳戶餘額。"}}]})
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "tool_calls": [{"id": str(count), "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}]}}]})

    with TestClient(create_app(database=tmp_path / "calculation.db", transport=httpx.MockTransport(model), api_key="test", model="test")) as client:
        response = client.post("/api/chat", json={"message": "依學生每日及每分鐘政策，今天用了8次、當分鐘用了4次，現在還能送多少？"})
        assert response.status_code == 200
        body = response.json()
        assert "1 次" in body["reply"]
        trace = body["tool_traces"][1]
        assert trace["arguments"] == {"limits": limits}
        assert trace["result"]["data"]["sendable_now"] == 1
        assert trace["result"]["data"]["limits"][0]["article_id"] == "H04"


@pytest.mark.parametrize("case,code,status", [("missing", "INVALID_ARGUMENT", 200), ("unknown", "NOT_FOUND", 200), ("unavailable", "INTERNAL_ERROR", 502)])
def test_calculation_errors_reach_chat_trace(tmp_path: Path, case: str, code: str, status: int) -> None:
    database = tmp_path / "demo.db"
    limit: dict[str, Any] = {"name": "每日", "window": "day", "maximum": 20, "used": 8, "source": "help_article", "article_id": "H04"}
    if case == "missing":
        del limit["used"]
    if case == "unknown":
        limit["article_id"] = "H99"
    calls = 0

    def model(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        body = json.loads(request.content)
        if calls == 1:
            message: dict[str, Any] = {"role": "assistant", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "calculate_remaining_requests", "arguments": json.dumps({"limits": [limit]})}}]}
        else:
            assert json.loads(body["messages"][-1]["content"])["error"]["code"] == code
            message = {"role": "assistant", "content": "資料不足，尚無法完成計算。"}
        return httpx.Response(200, json={"choices": [{"message": message}]})

    with TestClient(create_app(database=database, transport=httpx.MockTransport(model), api_key="test", model="test")) as client:
        if case == "unavailable":
            database.unlink()
        response = client.post("/api/chat", json={"message": "計算剩餘次數"})
        assert response.status_code == status
        assert response.json()["tool_traces"][0]["result"]["error"]["code"] == code
        assert "data" not in response.json()["tool_traces"][0]["result"]
        assert calls == (1 if case == "unavailable" else 2)


@pytest.mark.parametrize("case,code,status", [("normal", "", 200), ("invalid", "INVALID_ARGUMENT", 200), ("missing", "NOT_FOUND", 200), ("failure", "INTERNAL_ERROR", 502)])
def test_human_support_chat_results_and_errors(tmp_path: Path, case: str, code: str, status: int) -> None:
    import sqlite3

    db = tmp_path / "support.db"
    calls = 0
    arguments = {"reason": "invalid" if case == "invalid" else "login"}

    def model(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        body = json.loads(request.content)
        if calls == 1:
            message: dict[str, Any] = {"role": "assistant", "tool_calls": [{"id": "h1", "type": "function", "function": {"name": "get_human_support", "arguments": json.dumps(arguments)}}]}
        else:
            result = json.loads(body["messages"][-1]["content"])
            if code:
                assert result["error"]["code"] == code
            else:
                assert result["data"]["article_id"] == "H08"
                assert result["data"]["handoff_completed"] is False
                assert result["data"]["channel_configured"] is False
                assert result["data"]["simulated"] is True
            message = {"role": "assistant", "content": "模擬服務尚未完成真人交接。"}
        return httpx.Response(200, json={"choices": [{"message": message}]})

    with TestClient(create_app(database=db, transport=httpx.MockTransport(model), api_key="test", model="test")) as client:
        if case == "missing":
            with sqlite3.connect(db) as conn:
                conn.execute("DELETE FROM help_articles WHERE article_id = ?", ("H08",))
        if case == "failure":
            db.unlink()
        response = client.post("/api/chat", json={"message": "一直無法登入，想找人工"})
        assert response.status_code == status
        trace = response.json()["tool_traces"][0]
        assert trace["tool_name"] == "get_human_support"
        assert trace["arguments"] == arguments
        if code:
            assert trace["result"]["error"]["code"] == code
        else:
            assert trace["result"]["data"]["handoff_completed"] is False
        assert calls == (1 if case == "failure" else 2)


def test_multiturn_tool_context_is_isolated_and_reset_discards_history(tmp_path: Path) -> None:
    from uuid import UUID

    def model(request: httpx.Request) -> httpx.Response:
        messages = json.loads(request.content)["messages"][1:]
        first_question = messages[0]["content"]
        if messages[-1]["role"] == "tool":
            result = json.loads(messages[-1]["content"])
            article = result["data"]["articles"][0]
            return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": article["article_id"] + "：" + article["content"]}}]})
        if len(messages) == 1 and first_question in ("學生每日額度", "教師每日額度"):
            answer: dict[str, Any] = {"role": "assistant", "tool_calls": [{"id": "quota", "type": "function", "function": {"name": "search_help_articles", "arguments": json.dumps({"query": first_question})}}]}
        elif len(messages) == 1:
            answer = {"role": "assistant", "content": "請先說明學生或教師及查詢主題。"}
        else:
            assert messages[-1]["content"] == "那是多少次？"
            results = [json.loads(m["content"])["data"]["articles"][0] for m in messages if m["role"] == "tool"]
            assert len(results) == 1
            article = results[0]
            expected = "H04" if first_question == "學生每日額度" else "H05"
            assert article["article_id"] == expected
            assert article["request_limit"] == (20 if expected == "H04" else 40)
            assert all(("教師" if expected == "H04" else "學生") not in m.get("content", "") for m in messages if m["role"] in ("user", "assistant") and m.get("content"))
            answer = {"role": "assistant", "content": f"{expected} 模擬每日 {article['request_limit']} 次"}
        return httpx.Response(200, json={"choices": [{"message": answer}]})

    with TestClient(create_app(database=tmp_path / "sessions.db", transport=httpx.MockTransport(model), api_key="test", model="test")) as client:
        a = client.post("/api/chat", json={"message": "學生每日額度"}).json()
        b = client.post("/api/chat", json={"message": "教師每日額度"}).json()
        assert UUID(a["session_id"]) != UUID(b["session_id"])
        for initial, expected in [(a, "H04 模擬每日 20 次"), (b, "H05 模擬每日 40 次")]:
            followup = client.post("/api/chat", json={"session_id": initial["session_id"], "message": "那是多少次？"}).json()
            assert followup["session_id"] == initial["session_id"]
            assert followup["reply"] == expected
            assert followup["tool_traces"] == []
            assert len(initial["tool_traces"]) == 1
        assert client.post("/api/reset", json={"session_id": a["session_id"]}).json() == {"ok": True}
        assert client.post("/api/chat", json={"session_id": a["session_id"], "message": "那是多少次？"}).status_code == 404
        fresh = client.post("/api/chat", json={"message": "那是多少次？"}).json()
        assert fresh["session_id"] not in (a["session_id"], b["session_id"])
        assert fresh["reply"] == "請先說明學生或教師及查詢主題。"
        assert fresh["tool_traces"] == []
        assert client.post("/api/chat", json={"session_id": b["session_id"], "message": "那是多少次？"}).json()["reply"] == "H05 模擬每日 40 次"
        assert client.post("/api/reset", json={"session_id": a["session_id"]}).status_code == 200


@pytest.mark.parametrize("payload", [None, {"choices": [{"message": None}]}])
def test_malformed_model_response_stops_safely(tmp_path: Path, payload: Any) -> None:
    def model(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload) if payload is not None else httpx.Response(200, content="null")

    with TestClient(create_app(database=tmp_path / "malformed.db", transport=httpx.MockTransport(model), api_key="secret", model="test")) as client:
        response = client.post("/api/chat", json={"message": "429"})
        assert response.status_code == 502
        assert response.json()["tool_traces"] == []
        assert "稍後重試" in response.json()["reply"]
        assert "secret" not in response.text


@pytest.mark.parametrize("failure", ["http", "timeout", "limit", "tool"])
def test_failed_turn_retains_trace_and_retry_uses_only_committed_history(tmp_path: Path, failure: str) -> None:
    database = tmp_path / "retry.db"
    requests: list[dict[str, Any]] = []
    phase = "seed"
    calls = 0

    def model(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        body = json.loads(request.content)
        requests.append(body)
        if phase in ("seed", "retry"):
            answer: dict[str, Any] = {"role": "assistant", "content": "請提供查詢主題。"}
        else:
            calls += 1
            if calls > 1 and failure == "http":
                return httpx.Response(503, json={"error": "private-provider-detail"})
            if calls > 1 and failure == "timeout":
                raise httpx.ReadTimeout("private-provider-detail", request=request)
            answer = {"role": "assistant", "tool_calls": [{"id": str(calls), "type": "function", "function": {"name": "search_help_articles", "arguments": '{"query":"429"}'}}]}
        return httpx.Response(200, json={"choices": [{"message": answer}]})

    with TestClient(create_app(database=database, transport=httpx.MockTransport(model), api_key="test", model="test")) as client:
        seed = client.post("/api/chat", json={"message": "你好"}).json()
        phase = "failure"
        if failure == "tool":
            database.unlink()
        response = client.post("/api/chat", json={"session_id": seed["session_id"], "message": "失敗的問題"})
        assert response.status_code == 502
        body = response.json()
        assert body["session_id"] == seed["session_id"]
        assert len(body["tool_traces"]) == (6 if failure == "limit" else 1)
        assert calls == {"http": 2, "timeout": 2, "limit": 6, "tool": 1}[failure]
        assert "private-provider-detail" not in response.text
        assert "成功" not in body["reply"]
        assert body["tool_traces"][0]["result"]["ok"] is (failure != "tool")
        phase = "retry"
        retry = client.post("/api/chat", json={"session_id": seed["session_id"], "message": "重試問題"})
        assert retry.status_code == 200
        messages = requests[-1]["messages"][1:]
        assert [message["role"] for message in messages] == ["user", "assistant", "user"]
        assert messages[0]["content"] == "你好"
        assert messages[-1]["content"] == "重試問題"
        assert "失敗的問題" not in json.dumps(messages, ensure_ascii=False)

"""Reproducible external-model faults; not model-quality evidence.

Use a dedicated temporary database. Never point this fixture at user data.
"""
import json
from pathlib import Path

import httpx

from backend.main import create_app

DATABASE = Path("/tmp/campus-failure-browser.db")


def respond(request: httpx.Request) -> httpx.Response:
    messages = json.loads(request.content)["messages"]
    question = next(m["content"] for m in reversed(messages) if m["role"] == "user")
    if question == "測試工具內部錯誤":
        DATABASE.unlink(missing_ok=True)
    if question == "測試模型失敗" and messages[-1]["role"] == "tool":
        return httpx.Response(503, json={"error": "controlled provider failure"})
    if question not in ("測試模型失敗", "測試工具內部錯誤", "測試呼叫上限"):
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "【受控測試】請輸入測試模型失敗、測試工具內部錯誤或測試呼叫上限。"}}]})
    answer = {"role": "assistant", "tool_calls": [{"id": str(len(messages)), "type": "function", "function": {"name": "search_help_articles", "arguments": '{"query":"429"}'}}]}
    return httpx.Response(200, json={"choices": [{"message": answer}]})


app = create_app(database=DATABASE, api_key="controlled", model="controlled", transport=httpx.MockTransport(respond))

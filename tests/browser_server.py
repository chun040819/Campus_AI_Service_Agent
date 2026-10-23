"""Controlled browser fixture; never use for real-model acceptance."""
import json
from pathlib import Path

import httpx

from backend.main import create_app


def respond(request: httpx.Request) -> httpx.Response:
    messages = json.loads(request.content)["messages"]
    if messages[-1]["role"] == "tool":
        result = json.loads(messages[-1]["content"])
        text = result["data"]["articles"][0]["content"] if result["ok"] else "查無符合資料，請換具體關鍵字。"
        message = {"role": "assistant", "content": "【受控瀏覽器測試】" + text}
    else:
        message = {"role": "assistant", "content": None, "tool_calls": [{"id": "browser-call", "type": "function", "function": {"name": "search_help_articles", "arguments": '{"query":"429"}'}}]}
    return httpx.Response(200, json={"choices": [{"message": message}]})


app = create_app(database=Path("/tmp/campus-browser.db"), api_key="controlled", model="controlled", transport=httpx.MockTransport(respond))

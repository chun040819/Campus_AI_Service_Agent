"""Controlled Session browser fixture, not model-quality evidence."""
import asyncio
import json
from pathlib import Path

import httpx

from backend.main import create_app


async def respond(request: httpx.Request) -> httpx.Response:
    await asyncio.sleep(1)
    messages = json.loads(request.content)["messages"]
    if messages[-1]["role"] == "tool":
        article = json.loads(messages[-1]["content"])["data"]["articles"][0]
        answer = {"role": "assistant", "content": "【受控測試】" + article["content"]}
    elif len(messages) > 2:
        answer = {"role": "assistant", "content": "【受控測試】依前文 H04，模擬學生每日20次。"}
    elif messages[-1]["content"] == "那是多少次？":
        answer = {"role": "assistant", "content": "【受控測試】沒有前文，請先說明查詢主題。"}
    else:
        answer = {"role": "assistant", "content": None, "tool_calls": [{"id": "session-call", "type": "function", "function": {"name": "search_help_articles", "arguments": '{"query":"學生每日額度"}'}}]}
    return httpx.Response(200, json={"choices": [{"message": answer}]})


app = create_app(database=Path("/tmp/campus-session-browser.db"), api_key="controlled", model="controlled", transport=httpx.MockTransport(respond))

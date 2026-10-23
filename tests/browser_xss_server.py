"""Controlled hostile model output for browser escaping verification only."""
import json
from pathlib import Path

import httpx
from backend.main import create_app

PAYLOAD = '<img src=x onerror="window.__campusXss=1"><script>window.__campusXss=2</script>'


def respond(request: httpx.Request) -> httpx.Response:
    messages = json.loads(request.content)["messages"]
    if messages[-1]["role"] == "tool":
        answer = {"role": "assistant", "content": PAYLOAD}
    else:
        answer = {"role": "assistant", "tool_calls": [{"id": "xss", "type": "function", "function": {"name": PAYLOAD, "arguments": json.dumps({"query": PAYLOAD})}}]}
    return httpx.Response(200, json={"choices": [{"message": answer}]})


app = create_app(database=Path("/tmp/campus-xss-browser.db"), api_key="controlled", model="controlled", transport=httpx.MockTransport(respond))

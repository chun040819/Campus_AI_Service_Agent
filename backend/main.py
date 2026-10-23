import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from backend.agent import AgentFailure, run_agent
from backend.database import import_articles
from backend.tools.help_articles import create_registry

ROOT = Path(__file__).resolve().parent.parent


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    session_id: str | None = Field(default=None, max_length=64)
    message: str = Field(min_length=1, max_length=4000)


class ResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str = Field(min_length=1, max_length=64)


def create_app(*, database: Path | None = None, transport: httpx.AsyncBaseTransport | None = None, api_key: str | None = None, model: str | None = None) -> FastAPI:
    load_dotenv(ROOT / ".env")
    db = database or Path(os.getenv("DATABASE_PATH", str(ROOT / "var/demo.db")))
    key = api_key if api_key is not None else os.getenv("LLM_API_KEY", "")
    model_name = model if model is not None else os.getenv("LLM_MODEL", "")
    sessions: dict[str, list[dict[str, Any]]] = {}
    lock = asyncio.Lock()
    registry = create_registry(db)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        import_articles(ROOT / "data/help_articles.csv", db)
        async with httpx.AsyncClient(base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1/").rstrip("/") + "/", headers={"Authorization": f"Bearer {key}"}, timeout=30, transport=transport) as client:
            app.state.llm = client
            yield

    app = FastAPI(lifespan=lifespan)

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/chat", response_model=None)
    async def chat(request: ChatRequest) -> Any:
        if not key or not model_name:
            raise HTTPException(503, "請先於後端設定模型服務。")
        async with lock:
            sid = request.session_id or str(uuid4())
            if request.session_id and sid not in sessions:
                raise HTTPException(404, "對話不存在，請清除後重新開始。")
            if not request.session_id and len(sessions) >= 100:
                raise HTTPException(503, "示範服務對話已滿，請先清除舊對話。")
            history = sessions.get(sid, [])
            if len(history) >= 200:
                raise HTTPException(409, "對話已達上限，請清除後重新開始。")
            try:
                reply, traces, updated = await run_agent(app.state.llm, model_name, registry, history, request.message)
            except AgentFailure as exc:
                sessions.setdefault(sid, history)
                return JSONResponse(status_code=502, content={"session_id": sid, "reply": str(exc), "tool_traces": exc.traces, "error": "MODEL_FAILURE"})
            sessions[sid] = updated
            return {"session_id": sid, "reply": reply, "tool_traces": traces}

    @app.post("/api/reset")
    async def reset(request: ResetRequest) -> dict[str, bool]:
        async with lock:
            sessions.pop(request.session_id, None)
        return {"ok": True}

    return app


app = create_app()

"""Run the frozen routing cases against the configured real backend (no mocks).

Usage: .venv/bin/python -m scripts.evaluate_routing --output docs/issue-9-first.json
Each case gets a fresh session, removed after capture. Never writes credentials.
"""

import argparse
import asyncio
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

from backend.main import ROOT, create_app


def routing_matches(names: list[str], stages: list[list[str]]) -> bool:
    """Every stage must occur in order, allowing repeated calls within a stage."""
    if not stages:
        return not names
    stage = 0
    seen = False
    for name in names:
        if name in stages[stage]:
            seen = True
        elif seen and stage + 1 < len(stages) and name in stages[stage + 1]:
            stage += 1
            seen = True
        else:
            return False
    return seen and stage == len(stages) - 1


async def evaluate(cases_path: Path, output: Path) -> None:
    raw = cases_path.read_bytes()
    cases = json.loads(raw)
    # Load the same backend configuration and real HTTP model client as production.
    app = create_app()
    report: dict[str, Any] = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "provider_host": urlsplit(os.getenv("LLM_BASE_URL", "https://api.openai.com/v1/")).hostname,
        "model": os.getenv("LLM_MODEL", ""),
        "cases_sha256": hashlib.sha256(raw).hexdigest(),
        "cases": [],
        "metric": "HTTP 200 and ordered tool-name stages; content requires manual review",
    }
    if output.exists():
        raise FileExistsError("Choose a new output path to preserve earlier attempts")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Reserve the filename before spending model requests.
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://evaluation") as client:
            for case in cases:
                response = await client.post("/api/chat", json={"message": case["question"]})
                body = response.json()
                names = [trace["tool_name"] for trace in body.get("tool_traces", [])]
                passed = response.status_code == 200 and routing_matches(names, case["stages"])
                report["cases"].append({**case, "status": response.status_code, "actual_tools": names, "routing_pass": passed, "reply": body.get("reply", body.get("detail", "")), "tool_traces": body.get("tool_traces", [])})
                if body.get("session_id"):
                    await client.post("/api/reset", json={"session_id": body["session_id"]})
                report["routing_correct"] = sum(item["routing_pass"] for item in report["cases"])
                report["completed"] = len(report["cases"])
                output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
                print(f"{case['id']}: HTTP {response.status_code}, routing={'PASS' if passed else 'FAIL'}", flush=True)
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=ROOT / "docs/issue-9-cases.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(evaluate(args.cases, args.output))

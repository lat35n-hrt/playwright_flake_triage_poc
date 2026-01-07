# backend/app/main.py
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, Request
from fastapi.responses import JSONResponse

from app.flake import DelayConfig, DelayInjector
from app.settings import settings

from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse



app = FastAPI(title="Playwright Flake Triage PoC - Mock API")

# Resolve project root: .../playwright_flake_triage_poc
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

LOG_PATH = ARTIFACTS_DIR / settings.log_filename

# Template setup
templates = Jinja2Templates(directory=str(PROJECT_ROOT / "backend" / "app" / "templates"))


injector = DelayInjector(
    DelayConfig(
        seed=settings.flake_seed,
        min_ms=settings.delay_min_ms,
        max_ms=settings.delay_max_ms,
        prob=settings.delay_prob,
    )
)

# Avoid interleaving JSONL lines under concurrency
import asyncio
_jsonl_lock = asyncio.Lock()


async def append_jsonl(record: dict[str, Any]) -> None:
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
    async with _jsonl_lock:
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


async def inject_delay(request: Request) -> int:
    delay_ms = await injector.inject()
    request.state.injected_delay_ms = delay_ms
    return delay_ms


@app.middleware("http")
async def jsonl_logging_middleware(request: Request, call_next):
    start = time.perf_counter()

    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    request.state.request_id = request_id
    request.state.injected_delay_ms = 0

    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-Id"] = request_id
        return response
    finally:
        elapsed_ms = round((time.perf_counter() - start) * 1000.0, 3)
        record = {
            "ts_epoch_ms": int(time.time() * 1000),
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "query": str(request.url.query) if request.url.query else "",
            "status": status_code,
            "injected_delay_ms": int(getattr(request.state, "injected_delay_ms", 0)),
            "elapsed_ms": elapsed_ms,
            "flake_seed": settings.flake_seed,
            "delay_min_ms": settings.delay_min_ms,
            "delay_max_ms": settings.delay_max_ms,
            "delay_prob": settings.delay_prob,
        }
        await append_jsonl(record)


# --- Mock data ---
_ITEMS = [{"id": i, "name": f"Item {i}"} for i in range(1, 6)]


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"ok": True}


@app.get("/api/items")
async def list_items(request: Request) -> dict[str, Any]:
    await inject_delay(request)
    return {"items": _ITEMS}


@app.get("/api/items/{item_id}")
async def get_item(item_id: int, request: Request):
    await inject_delay(request)
    item = next((x for x in _ITEMS if x["id"] == item_id), None)
    if item is None:
        return JSONResponse(status_code=404, content={"error": "not_found", "id": item_id})
    return {"item": item, "detail": {"description": f"Details for item {item_id}"}}


@app.post("/api/items/{item_id}/approve")
async def approve_item(item_id: int, request: Request):
    await inject_delay(request)
    item = next((x for x in _ITEMS if x["id"] == item_id), None)
    if item is None:
        return JSONResponse(status_code=404, content={"error": "not_found", "id": item_id})
    return {"id": item_id, "status": "approved"}


@app.get("/", response_class=HTMLResponse)
async def ui_index(request: Request):
    # overlay config is injected into global JS variable
    html = templates.get_template("index.html").render()
    # inject window.__OVERLAY_MS__
    injected = html.replace(
        "</head>",
        f"<script>window.__OVERLAY_MS__ = {settings.ui_overlay_ms};</script></head>"
    )
    return HTMLResponse(injected)


@app.get("/items/{item_id}", response_class=HTMLResponse)
async def ui_detail(item_id: int, request: Request):
    html = templates.get_template("detail.html").render(item_id=item_id)
    injected = html.replace(
        "</head>",
        f"<script>window.__OVERLAY_MS__ = {settings.ui_overlay_ms};</script></head>"
    )
    return HTMLResponse(injected)

@app.post("/api/items", status_code=201)
async def create_item(payload: dict = Body(...)):
    # PoC: minimal echo
    return payload
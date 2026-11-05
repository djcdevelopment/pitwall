"""FastAPI app. GET only, loopback only, no CORS, no proxying, no write routes."""

from __future__ import annotations

import os
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, JSONResponse

from .collector_loop import Store
from .config import Config, load
from .corrections import load_corrections
from .demo import Demo

_HOST_OK = re.compile(r"^(127\.0\.0\.1|localhost|\[::1\])(:\d+)?$")
NOSNIFF = {"X-Content-Type-Options": "nosniff"}


def _etag_matches(header: Optional[str], etag: str) -> bool:
    if not header:
        return False
    return any(p.strip().removeprefix("W/") == etag for p in header.split(","))


def create_app(cfg: Optional[Config] = None, store: Optional[Store] = None) -> FastAPI:
    cfg = cfg or load()
    store = store or Store(cfg)
    demo = Demo(cfg.fixtures_dir, load_corrections(cfg.corrections_path))

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        store.start()
        try:
            yield
        finally:
            store.stop()

    app = FastAPI(title="pitwall", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.store, app.state.demo, app.state.cfg = store, demo, cfg

    @app.middleware("http")
    async def guard(request: Request, call_next):
        # DNS-rebinding guard: only loopback Host headers are answered.
        if not _HOST_OK.match(request.headers.get("host", "")):
            return JSONResponse({"error": "host not allowed"}, status_code=403, headers=NOSNIFF)
        resp = await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        return resp

    def _mode(mode: str, scenario: Optional[str]) -> tuple[str, Optional[str]]:
        if mode not in ("live", "demo"):
            raise HTTPException(400, "mode must be live or demo")
        if mode == "demo":
            sid = scenario or demo.default()
            if not sid or demo.snapshot(sid) is None:
                raise HTTPException(404, "unknown scenario")
            return "demo", sid
        return "live", None

    @app.get("/api/snapshot")
    def api_snapshot(request: Request, mode: str = "live", scenario: Optional[str] = None):
        m, sid = _mode(mode, scenario)
        if m == "demo":
            snap, body = demo.snapshot(sid)  # type: ignore[arg-type,misc]
            seq = snap.seq
        else:
            snap, body, seq = store.snapshot()
            if snap is None:
                raise HTTPException(503, "no snapshot yet")
        etag = f'"{seq}-{m}-{sid or ""}"'
        if _etag_matches(request.headers.get("if-none-match"), etag):
            return Response(status_code=304, headers={"ETag": etag, "Cache-Control": "no-cache"})
        return Response(content=body, media_type="application/json", headers={"ETag": etag, "Cache-Control": "no-cache"})

    @app.get("/api/history")
    def api_history(window: int = 300, mode: str = "live", scenario: Optional[str] = None):
        if window not in (60, 300, 900):
            raise HTTPException(400, "window must be 60, 300 or 900")
        m, sid = _mode(mode, scenario)
        h = demo.history(sid, window, time.time()) if m == "demo" else store.get_history(window)  # type: ignore[arg-type]
        return Response(content=h.model_dump_json(), media_type="application/json", headers={"Cache-Control": "no-cache"})  # type: ignore[union-attr]

    @app.get("/api/evidence/{task_id}")
    def api_evidence_index(task_id: str, mode: str = "live"):
        if mode == "demo":
            raise HTTPException(404, "evidence is unavailable in demo mode")
        idx = store.evidence.index(task_id)
        if idx is None:
            raise HTTPException(404, "unknown task")
        return Response(content=idx.model_dump_json(), media_type="application/json", headers={"Cache-Control": "no-cache"})

    @app.get("/api/evidence/{task_id}/{record_id}")
    def api_evidence_record(task_id: str, record_id: str, mode: str = "live"):
        if mode == "demo":
            raise HTTPException(404, "evidence is unavailable in demo mode")
        got = store.evidence.content(task_id, record_id)
        if got is None:
            raise HTTPException(404, "unknown record")
        media, body, _ = got
        return Response(content=body, media_type=media, headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-cache"})

    @app.get("/api/scenarios")
    def api_scenarios():
        return {"scenarios": demo.scenarios(), "note": demo.spec.get("note", "")}

    @app.get("/api/health")
    def api_health():
        return store.health()

    # Static, after the API routes. SPA index for unknown non-API paths.
    @app.get("/{path:path}", include_in_schema=False)
    def static(path: str):
        if path.startswith("api/") or path == "api":
            raise HTTPException(404, "not found")
        dist = Path(cfg.web_dist)
        if not dist.is_dir():
            raise HTTPException(404, "web/dist not built")
        root = os.path.realpath(dist)
        target = os.path.realpath(dist / path) if path else os.path.join(root, "index.html")
        if not (target == root or target.startswith(root + os.sep)):
            raise HTTPException(404, "not found")
        if os.path.isdir(target):
            target = os.path.join(target, "index.html")
        if not os.path.isfile(target):
            target = os.path.join(root, "index.html")
            if not os.path.isfile(target):
                raise HTTPException(404, "not found")
        return FileResponse(target)

    return app

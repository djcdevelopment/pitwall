"""Collector threads and the lock-protected last-good state served by the API.

fleet and flow each poll in their own daemon thread (2 s). A ticker rebuilds the snapshot so ages keep
advancing even if a source is wedged. /api/snapshot only reads the prebuilt state; it never waits on a
collector, a subprocess or a receipt scan.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import threading
import time
from typing import Optional

from .config import Config
from .contract import History, Snapshot, SourceRecord
from .corrections import load_corrections
from .evidence import Evidence
from .history import HistoryRing
from .normalize import Ctx, build_snapshot
from .participation import ReceiptView
from .sources import CacheSource, SourceState
from .sources import fleet as fleet_src
from .sources import flow as flow_src
from .sources.receipts import ReceiptReader
from .sources.endpoints import load_identity, observe
from .sources.version import read_version
from .endpoint_services import build as build_endpoint_services
from .util import iso_from_epoch, now_iso

_VOLATILE = {"generated_at", "read_at", "age_s"}


def _strip(o):
    if isinstance(o, dict):
        return {k: _strip(v) for k, v in o.items() if k not in _VOLATILE}
    if isinstance(o, list):
        return [_strip(v) for v in o]
    return o


def source_record(st: SourceState, now: float) -> SourceRecord:
    return SourceRecord(id=st.id, label=st.label, state=st.state(now), path=st.path,  # type: ignore[arg-type]
                        observed_at=iso_from_epoch(st.observed_epoch), read_at=iso_from_epoch(st.read_epoch),
                        age_s=round(st.age_s(now), 1) if st.age_s(now) is not None else None,
                        stale_after_s=st.stale_after_s, last_error=st.last_error)


class Store:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.fleet: CacheSource = fleet_src.make(cfg)
        self.flow: CacheSource = flow_src.make(cfg)
        self.reader = ReceiptReader()
        self.evidence = Evidence(cfg.run_roots)
        self.history = HistoryRing()
        self.corrections = load_corrections(cfg.corrections_path)
        self.started = time.time()
        self._lock = threading.Lock()          # guards the published state below
        self._build_lock = threading.Lock()    # one rebuild at a time
        self._snap: Optional[Snapshot] = None
        self._body: bytes = b""
        self._seq = 0
        self._digest = ""
        self._fleet_seen = -1
        self._flow_seen = -1
        self._stop = threading.Event()
        self._versions: dict[str, tuple[float, object]] = {}
        self.identity = load_identity(cfg.endpoints_path)
        self._endpoints: Optional[dict] = None
        self._threads: list[threading.Thread] = []

    # -- lifecycle -----------------------------------------------------------------------------
    def start(self) -> None:
        self.rebuild()
        for name, fn in (("pitwall-fleet", lambda: self._loop(self.fleet)), ("pitwall-flow", lambda: self._loop(self.flow)), ("pitwall-tick", self._tick), ("pitwall-endpoints", self._endpoint_loop)):
            t = threading.Thread(target=fn, name=name, daemon=True)
            t.start()
            self._threads.append(t)

    def stop(self) -> None:
        self._stop.set()

    def _loop(self, src: CacheSource) -> None:
        while not self._stop.is_set():
            try:
                src.poll()
                self.rebuild()
            except Exception:  # noqa: BLE001 - a collector failure must not end the thread
                pass
            self._stop.wait(self.cfg.poll_s)

    def _endpoint_loop(self) -> None:
        """Own thread: a slow or wedged probe delays only these rows."""
        while not self._stop.is_set():
            try:
                self._endpoints = observe(self.identity, time.time())
            except Exception:  # noqa: BLE001 - a probe failure must not end the thread
                pass
            self._stop.wait(self.cfg.endpoints_poll_s)

    def _tick(self) -> None:
        while not self._stop.is_set():
            self._stop.wait(self.cfg.poll_s)
            try:
                self.rebuild(blocking=False)
            except Exception:  # noqa: BLE001
                pass

    def _version(self, repo: str, now: float):
        seen = self._versions.get(repo)
        if seen is None or now - seen[0] >= self.cfg.version_ttl_s:
            seen = (now, read_version(repo, now))
            self._versions[repo] = seen
        return seen[1]

    # -- build ---------------------------------------------------------------------------------
    def rebuild(self, blocking: bool = True) -> None:
        if not self._build_lock.acquire(blocking=blocking):
            return
        try:
            now = time.time()
            fl, fw = self.fleet.state, self.flow.state
            fleet_rec, flow_rec = source_record(fl, now), source_record(fw, now)
            fleet_rec.version, flow_rec.version = self._version(self.cfg.fleet_repo, now), self._version(self.cfg.flow_repo, now)
            flow_tasks = [t for t in ((fw.data or {}).get("tasks") or []) if isinstance(t, dict)][:10]
            tasks = [(str(t.get("task_id")), str(t.get("run_dir") or "")) for t in flow_tasks]
            names = self.evidence.refresh(tasks)
            views: dict[str, ReceiptView] = {}
            for tid, rd in tasks:
                v = self.reader.read(rd) if rd else ReceiptView()
                views[tid] = dataclasses.replace(v, record_ids=names.get(tid, {}))
            receipts_rec = SourceRecord(id="receipts", label="Run directory receipts", state="idle", path="run_directories", observed_at=None,
                                        read_at=iso_from_epoch(now), age_s=None, stale_after_s=0.0, last_error="")
            ctx = Ctx(mode="live", scenario=None, read_at=iso_from_epoch(now) or "", corrections=self.corrections,
                      evidence_tasks={tid for tid, recs in names.items() if recs},
                      history_started_at=iso_from_epoch(self.history.started_at))
            ep = self._endpoints
            ep_epoch = ep["observed_epoch"] if ep else None
            ep_age = round(now - ep_epoch, 1) if ep_epoch else None
            ep_rows, ep_links = build_endpoint_services(self.identity, ep, iso_from_epoch(now) or "", iso_from_epoch(ep_epoch), ep_age)
            ep_rec = SourceRecord(id="endpoints", label="Endpoint probes", state="idle" if ep and ep_age is not None and ep_age <= 60 else "stale" if ep else "unknown",
                                  path="direct_probes", observed_at=iso_from_epoch(ep_epoch), read_at=iso_from_epoch(now), age_s=ep_age, stale_after_s=60.0)
            snap = build_snapshot(ctx=ctx, generated_at=now_iso(), fleet=fl.data, flow=fw.data, fleet_rec=fleet_rec, flow_rec=flow_rec,
                                  receipts_rec=receipts_rec, views=views, endpoint_rows=ep_rows if self.identity else None,
                                  endpoint_links=ep_links, endpoints_rec=ep_rec if self.identity else None)
            # history: one sample per new fleet observation; gaps only when stale
            self.history.record_fleet(snap, fl.observed_epoch, advanced=fl.obs_count != self._fleet_seen,
                                      stale=fleet_rec.state in ("stale", "unreachable") and (fl.age_s(now) is None or fl.age_s(now) > fl.stale_after_s), now=now)
            snap.history_started_at = iso_from_epoch(self.history.started_at)
            payload = _strip(json.loads(snap.model_dump_json(by_alias=True)))
            digest = hashlib.sha256(json.dumps([payload, fl.obs_count, fw.obs_count], sort_keys=True).encode()).hexdigest()
            with self._lock:
                if digest != self._digest:
                    self._digest = digest
                    self._seq += 1
                snap.seq = self._seq
                self._snap = snap
                self._body = snap.model_dump_json(by_alias=True).encode("utf-8")
            self._fleet_seen, self._flow_seen = fl.obs_count, fw.obs_count
        finally:
            self._build_lock.release()

    # -- reads (never block on collectors) -----------------------------------------------------------
    def snapshot(self) -> tuple[Optional[Snapshot], bytes, int]:
        with self._lock:
            return self._snap, self._body, self._seq

    def get_history(self, window_s: int) -> History:
        return self.history.get(window_s, time.time())

    def health(self) -> dict:
        now = time.time()
        return {
            "status": "ok", "service": "pitwall", "schema": "pitwall.v1", "uptime_s": round(now - self.started, 1), "seq": self._seq,
            "sources": [{"id": s.state.id, "state": s.state.state(now), "path": s.state.path, "observed_at": iso_from_epoch(s.state.observed_epoch),
                         "age_s": round(s.state.age_s(now), 1) if s.state.age_s(now) is not None else None, "last_error": s.state.last_error}
                        for s in (self.fleet, self.flow)],
        }

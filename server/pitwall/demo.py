"""Demo mode: committed fixtures through the same normalizer. Reads no real run directories."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from . import participation as P
from .contract import History, Snapshot, SourceRecord
from .history import demo_history
from .normalize import Ctx, build_snapshot
from .util import iso_from_epoch, now_iso, to_float

FLEET_STALE = 0.0  # fixtures do not age


def _hop(ft: dict, hop_id: str) -> dict:
    for h in ft.get("observed_hops", []) or []:
        if isinstance(h, dict) and h.get("hop_id") == hop_id:
            return h
    return {}


def synth_view(ft: dict, scenario: str) -> P.ReceiptView:
    """A synthetic ReceiptView from a flow-top task row's own fields. Never touches disk."""
    files: dict[str, int] = {}
    data: dict[str, Any] = {}
    lines: dict[str, list[dict]] = {}

    def put(name: str, obj: Any) -> None:
        files[name] = 0
        if isinstance(obj, list):
            lines[name] = obj
        else:
            data[name] = obj

    if ft.get("broker_receipt_path"):
        q, mid = ft.get("broker_queue"), ft.get("broker_message_id")
        ents = []
        if ft.get("broker_send_at"):
            ents.append({"kind": "send_acknowledged", "at": ft["broker_send_at"], "queue": q, "message_id": mid})
        if ft.get("broker_recv_at"):
            ents.append({"kind": "received_peek_lock", "at": ft["broker_recv_at"], "queue": q, "message_id": mid,
                         "sequence_number": ft.get("broker_sequence_number"), "delivery_count": ft.get("broker_delivery_count")})
        if ft.get("broker_settle_at"):
            ents.append({"kind": "completed", "at": ft["broker_settle_at"], "queue": q, "message_id": mid,
                         "sequence_number": ft.get("broker_sequence_number")})
        if ents:
            put("BROKER-RECEIPTS.jsonl", ents)
    if ft.get("hearth_execution_path"):
        ex: dict[str, Any] = {"provider": ft.get("hearth_provider"), "model": ft.get("hearth_model"), "job_id": ft.get("hearth_job_id"),
                              "status": ft.get("hearth_status"), "task_family": ft.get("task_family"), "routed_by": ft.get("selected_route"),
                              "created_at": _hop(ft, "hearth_27b").get("timestamp_utc") or None}
        n = ft.get("packed_files_count")
        if isinstance(n, int) and not isinstance(n, bool):
            ex["desired"] = {"packed_files": ["(fixture)"] * n}
        put("execution.json", ex)
    if ft.get("steppewise_events_path"):
        put("LOOKUP-MEASURE.json", {"started_at": _hop(ft, "ontology").get("timestamp_utc") or None, "duration_ms": ft.get("ontology_lookup_ms"),
                                    "execution": ft.get("steppewise_workflow") or ""})
    if ft.get("ontology_receipt_path"):
        files["DELIVERED-DEFINITION.json"] = 0
    m = re.search(r"warm=([\d.]+)ms vs cold=([\d.]+)ms", str(ft.get("text_cache_job_note", "")))
    if m and "hit=True" in str(ft.get("text_cache_job_note", "")):
        put("PACK-CACHE-RECEIPTS.json", {"cold_receipt": {"cache_hit": False, "duration_ms": float(m.group(2))},
                                          "warm_receipt": {"cache_hit": True, "duration_ms": float(m.group(1))}})
    dh = _hop(ft, "duckdb_transition")
    if dh.get("used_by_job") and str(dh.get("evidence_link", "")).endswith("DUCKDB-RECEIPT.json"):
        put("DUCKDB-RECEIPT.json", {"recorded_at": dh.get("timestamp_utc") or None, "read_back_verified": True,
                                    "tables": {"fixture_transition": {"row_count": 1}}})
    status = str(ft.get("irc_delivery_status", ""))
    if status in ("delivered", "recovered", "active"):
        mm = re.search(r"\((\d+) receipts\)", str(ft.get("irc_delivery_label", "")))
        put("IRC-RECEIPTS.jsonl", [{"kind": "fixture_receipt", "at": None} for _ in range(int(mm.group(1)) if mm else 1)])
    if status == "recovered":
        put("RECOVERY.json", {"application_recoveries": 1})
    completed = str(ft.get("outcome_label")) == "completed"
    if completed:
        rv = str(ft.get("review_status", "")).replace("review ", "").strip()
        put("consumption.json", {"parent": str(ft.get("actor", "")).split(" ")[0], "at": ft.get("last_progress_utc") or None,
                                 "action": ft.get("outcome") or "", "independent_review": rv if rv in ("pending", "accepted", "rejected") else ""})
        if str(ft.get("source_receipt_path", "")).endswith("RESULT.json"):
            put("RESULT.json", {"completed_at": ft.get("last_progress_utc") or None})
    chk = str(ft.get("check_artifact_path", ""))
    if chk.endswith("PARENT-CHECKS.json") and isinstance(ft.get("checks_passed"), bool):
        put("PARENT-CHECKS.json", {"passed": ft["checks_passed"]})
    elif chk.endswith("REVIEW-BUNDLE.json"):
        put("REVIEW-BUNDLE.json", {"checks": []})
    return P.ReceiptView(run_dir="fixture", files=files, dirs=set(), data=data, lines=lines, synthetic=True, label=f"demo:{scenario}")


class Demo:
    def __init__(self, fixtures_dir: str, corrections: list[dict]):
        self.dir = Path(fixtures_dir)
        self.corrections = corrections
        self._cache: dict[str, tuple[Snapshot, bytes]] = {}
        self._fleet: dict[str, dict] = {}
        try:
            self.spec = json.loads((self.dir / "scenarios.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.spec = {"scenarios": []}

    def scenarios(self) -> list[dict]:
        return [{"id": s["id"], "note": s.get("note", ""), "edited": s.get("edited", [])} for s in self.spec.get("scenarios", [])]

    def default(self) -> Optional[str]:
        sc = self.spec.get("scenarios", [])
        return sc[0]["id"] if sc else None

    def _scenario(self, sid: str) -> Optional[dict]:
        return next((s for s in self.spec.get("scenarios", []) if s.get("id") == sid), None)

    def _load(self, rel: str) -> dict:
        return json.loads((self.dir / rel).read_text(encoding="utf-8"))

    def snapshot(self, sid: str) -> Optional[tuple[Snapshot, bytes]]:
        if sid in self._cache:
            return self._cache[sid]
        sc = self._scenario(sid)
        if not sc:
            return None
        fleet, flow = self._load(sc["fleet"]), self._load(sc["flow"])
        self._fleet[sid] = fleet
        for p in sc.get("patches", []):
            tasks = flow.get("tasks", [])
            if tasks and p.get("field"):
                t = tasks[p.get("task_index", -1)]
                t[p["field"]] = str(t.get(p["field"], "")) + p.get("append", "")
        read_at = now_iso()
        ctx = Ctx(mode="demo", scenario=sid, read_at=read_at, corrections=[], scenario_note=sc.get("note", "") + " Demo data, not live.")
        recs = []
        for sid_, label, ts in (("fleet", "fleet-top (fixture)", fleet.get("timestamp_epoch")), ("flow", "flow-top (fixture)", flow.get("collected_at_unix"))):
            recs.append(SourceRecord(id=sid_, label=label, state="idle", path="fixture", observed_at=iso_from_epoch(to_float(ts)), read_at=read_at,
                                     age_s=None, stale_after_s=FLEET_STALE, last_error=""))
        recs.append(SourceRecord(id="receipts", label="Run directory receipts (synthetic view)", state="idle", path="fixture", observed_at=None,
                                 read_at=read_at, age_s=None, stale_after_s=FLEET_STALE, last_error=""))
        views = {str(t.get("task_id")): synth_view(t, sid) for t in flow.get("tasks", [])[:10] if isinstance(t, dict)}
        snap = build_snapshot(ctx=ctx, generated_at=read_at, fleet=fleet, flow=flow, fleet_rec=recs[0], flow_rec=recs[1], receipts_rec=recs[2], views=views)
        snap.seq = 1
        body = snap.model_dump_json(by_alias=True).encode("utf-8")
        self._cache[sid] = (snap, body)
        return self._cache[sid]

    def history(self, sid: str, window_s: int, now: float) -> Optional[History]:
        if self.snapshot(sid) is None:
            return None
        return demo_history(self._fleet[sid], window_s, now, sid)

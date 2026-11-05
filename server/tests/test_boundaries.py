"""Data-boundary tests only. No collector is ever invoked; demo and synthetic views feed everything."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path

import pytest

from pitwall import participation as P
from pitwall.config import REPO_ROOT
from pitwall.corrections import apply_fraction, load_corrections
from pitwall.contract import Measurement
from pitwall.demo import Demo, synth_view
from pitwall.evidence import Evidence, scrub_value
from pitwall.normalize import Ctx, build_task, norm_fleet, norm_services

FIX = str(REPO_ROOT / "fixtures")
CORR = str(REPO_ROOT / "config" / "corrections.json")


def ctx(mode="live", scenario=None):
    return Ctx(mode=mode, scenario=scenario, read_at="2026-11-05T00:00:00Z", corrections=load_corrections(CORR))


def fleet_with(**dev):
    base = {
        "device_id": "X#0", "host_id": "omen", "short_title": "X", "hardware_identity": "x", "mode": "serving", "workload_label": ":18091 m (0/8 reqs)",
        "owner_label": "o", "telemetry_age_s": 0.0, "reachable": True, "is_stale": False,
        "compute_util_pct": {"value": 0.0, "status": "ok", "age_s": None, "note": ""},
        "power_w": {"value": None, "status": "unavailable", "age_s": None, "note": ""},
        "power_limit_w": 230.0, "temp_core_c": {"value": None, "status": "unavailable", "age_s": None, "note": ""},
        "temp_vram_c": {"value": None, "status": "unavailable", "age_s": None, "note": ""},
        "vram_measured_used_gib": {"value": None, "status": "unavailable", "age_s": None, "note": ""},
        "vram_measured_total_gib": 31.9, "link_info": "",
    }
    base.update(dev)
    return {
        "timestamp_epoch": 1.0, "host_inventory": {"omen": "OMEN"}, "devices": [base], "endpoints": [], "active_jobs": [], "summary": {},
        "caches": {"kv_prefix_caches": [
            {"endpoint_id": "omen:18091", "model_id": "m", "hits": 0, "queries": 0, "hit_rate_pct": None, "unit": "tok", "time_window": "engine uptime", "online": True},
            {"endpoint_id": "am4:18094", "model_id": "m", "hits": 0, "queries": 2816554, "hit_rate_pct": 0.0, "unit": "tok", "time_window": "engine uptime", "online": True}]},
        "known_blind_spots": [],
    }


def test_null_never_becomes_zero_and_zero_cache_is_null():
    out = norm_fleet(fleet_with(), "idle", ctx())
    d = out["devices"][0]
    assert d.power.value is None and d.power.status == "unknown"          # unavailable reading is not 0
    assert d.temp_core.value is None and d.memory_used.value is None
    assert d.utilization.value == 0.0 and d.utilization.status == "ok"    # a measured zero stays 0
    c0, c1 = out["engine_caches"][0].hit, out["engine_caches"][1].hit
    assert c0.value is None and c0.numerator == 0 and c0.denominator == 0 and c0.status == "unknown"  # 0/0 stays null
    assert c1.value == 0.0 and c1.status == "ok" and c1.denominator == 2816554                         # 0.0% of 2.8M is a real 0
    unreachable = norm_fleet(fleet_with(reachable=False), "idle", ctx())["devices"][0]
    assert unreachable.power.value is None and unreachable.power.status == "unreachable" and unreachable.state == "unreachable"


def _flow_row(**kw):
    t = json.loads((Path(FIX) / "raw" / "flow-orland_completed.json").read_text())["tasks"][0]
    t = copy.deepcopy(t)
    t.update(kw)
    return t


def test_default_not_used_by_job_becomes_unknown_not_unused():
    ft = _flow_row(broker_receipt_path="", hearth_execution_path="", steppewise_events_path="", ontology_receipt_path="")
    for h in ft["observed_hops"]:
        h["state"], h["used_by_job"] = "not_used_by_job", False
    ft["jepa_job_state"] = ft["duckdb_job_state"] = ft["ontology_job_state"] = ft["steppewise_state"] = "not_used_by_job"
    task = build_task(ft, synth_view(ft, "t"), {}, ctx("demo", "t"))
    by = {h.component: h for h in task.path}
    for comp in ("service_bus", "steppewise", "ontology", "duckdb", "jepa", "ast_cache"):
        assert by[comp].state == "unknown", comp
        assert by[comp].basis.startswith("no ") or "no " in by[comp].basis


def test_jepa_unused_only_with_empty_packed_files():
    def hop(view):
        return {h.component: h for h in P.derive_path(view)}["jepa"]

    empty = P.ReceiptView(data={"execution.json": {"desired": {"packed_files": []}}})
    assert hop(empty).state == "unused"
    assert hop(empty).basis == "desired.packed_files=[] (execution.json)"
    assert hop(empty).summary == "not used for HEARTH file packing"
    assert hop(P.ReceiptView(data={"execution.json": {"desired": {"packed_files": ["a.py"]}}})).state == "used"
    assert hop(P.ReceiptView(data={"execution.json": {"desired": {}}})).state == "unknown"
    assert hop(P.ReceiptView()).state == "unknown"
    assert hop(P.ReceiptView(data={"submitted.json": {"desired": {"packed_files": []}}})).basis == "desired.packed_files=[] (submitted.json)"


def test_correction_overlay_keeps_3_of_9_and_4_of_9():
    view = P.ReceiptView(run_dir="/x", files={"RESULT.json": 1}, data={"RESULT.json": {"metrics": {
        "required_facts_covered_baseline": "4/9", "required_facts_covered_selected": "9/9"}}})
    ft = _flow_row(task_id="help-ontology-relpack-20261104")
    task = build_task(ft, view, {}, ctx())
    base = task.context.required_facts_baseline
    assert (base.numerator, base.denominator, base.value) == (3, 9, "3/9")
    assert "4/9" in base.note and "review-reported correction" in base.note and "verified" not in base.note
    assert task.context.corrections[0].displayed_value == "3/9" and task.context.corrections[0].producer_value == "4/9"
    assert (task.context.required_facts_selected.numerator, task.context.required_facts_selected.denominator) == (9, 9)
    # a different task is not corrected
    other = build_task(_flow_row(task_id="some-other"), view, {}, ctx())
    assert other.context.required_facts_baseline.value == "4/9" and other.context.corrections == []
    shown, corr = apply_fraction([], "t", "required_facts_baseline", Measurement(value="4/9"), "")
    assert shown.value == "4/9" and corr == []


def test_evidence_rejects_traversal_unknown_tasks_and_logs(tmp_path):
    root = tmp_path / "ops1"
    run = root / "run-a"
    run.mkdir(parents=True)
    (run / "RESULT.json").write_text('{"input_tokens": 5, "api_key": "sk-secret", "note": "Bearer abc.def"}')
    (run / "IRC-RECEIPTS.jsonl").write_text('{"kind":"x","raw_irc_line":"@time=1 :nick PRIVMSG"}\n')
    (run / "worker.log").write_text("secret log")
    (run / "helper-result.txt").write_text("txt")
    (run / "my-key.json").write_text("{}")
    (run / "big.duckdb").write_bytes(b"x")
    outside = tmp_path / "outside.json"
    outside.write_text('{"outside": true}')
    (run / "link.json").symlink_to(outside)
    ev = Evidence([str(root)])
    names = ev.refresh([("task-a", str(run)), ("task-bad", str(tmp_path / "elsewhere"))])
    idx = ev.index("task-a")
    assert idx is not None
    served = {r.name for r in idx.records}
    assert served == {"RESULT.json", "IRC-RECEIPTS.jsonl"}
    assert {"worker.log", "helper-result.txt", "my-key.json", "big.duckdb", "link.json"} <= set(idx.not_served)
    assert ev.index("task-unknown") is None and ev.index("../task-a") is None
    assert ev.index("task-bad").records == []                      # outside PITWALL_RUN_ROOTS: nothing registered
    rid = names["task-a"]["RESULT.json"]
    media, body, _ = ev.content("task-a", rid)
    text = body.decode()
    assert media.startswith("text/plain") and "sk-secret" not in text and "abc.def" not in text and '"input_tokens": 5' in text
    _, irc, _ = ev.content("task-a", names["task-a"]["IRC-RECEIPTS.jsonl"])
    assert "PRIVMSG" not in irc.decode() and "[redacted]" in irc.decode()
    for bad in ("../../etc/passwd", "worker.log", "..%2f", "0" * 16):
        assert ev.content("task-a", bad) is None
    assert ev.content("task-unknown", rid) is None and ev.content("task-bad", rid) is None
    assert scrub_value({"tokens_in": 3, "access_token": "x", "authorization": "y"}) == {"tokens_in": 3, "access_token": "[redacted]", "authorization": "[redacted]"}


def test_evidence_api_404s(tmp_path):
    from fastapi.testclient import TestClient
    from pitwall.app import create_app
    from pitwall.config import load

    run = tmp_path / "ops1" / "r"
    run.mkdir(parents=True)
    (run / "RESULT.json").write_text("{}")
    (run / "a.log").write_text("x")
    cfg = load()
    app = create_app(cfg)
    app.state.store.evidence = Evidence([str(tmp_path / "ops1")])
    names = app.state.store.evidence.refresh([("t1", str(run))])
    c = TestClient(app, base_url="http://127.0.0.1")
    assert c.get("/api/evidence/unknown").status_code == 404
    assert c.get("/api/evidence/t1/deadbeefdeadbeef").status_code == 404
    assert c.get("/api/evidence/t1?mode=demo").status_code == 404
    assert c.get("/api/evidence/t1").json()["not_served"] == ["a.log"]
    r = c.get(f"/api/evidence/t1/{names['t1']['RESULT.json']}")
    assert r.status_code == 200 and r.headers["x-content-type-options"] == "nosniff" and r.headers["content-type"].startswith("text/plain")
    assert c.get("/api/evidence/t1/..%2F..%2Fetc%2Fpasswd").status_code == 404
    assert c.post("/api/snapshot").status_code == 405
    assert c.get("/api/snapshot", headers={"host": "evil.example"}).status_code == 403


def test_completed_tasks_never_read_idle():
    demo = Demo(FIX, [])
    for sc in demo.scenarios():
        snap, _ = demo.snapshot(sc["id"])
        flow = json.loads((Path(FIX) / demo._scenario(sc["id"])["flow"]).read_text())
        by = {t["task_id"]: t for t in flow["tasks"]}
        for t in snap.tasks:
            assert t.outcome.state != "idle" and t.outcome.state in ("active", "staged", "completed", "recovered", "failed", "unknown")
            if by[t.id]["outcome_label"] == "completed":
                assert t.outcome.state in ("completed", "recovered"), (sc["id"], t.id)
                assert t.outcome.state != "active"


def test_help_loop_service_bus_is_unknown():
    view = P.ReceiptView(run_dir="/x", files={"execution.json": 1, "consumption.json": 1, "IRC-RECEIPTS.jsonl": 1},
                         data={"execution.json": {"provider": "omen-dense-27b", "status": "succeeded", "desired": {"packed_files": []}},
                               "consumption.json": {"parent": "cx-adhoc", "independent_review": "pending"}},
                         lines={"IRC-RECEIPTS.jsonl": [{"kind": "a"}]})
    sb = {h.component: h for h in P.derive_path(view)}["service_bus"]
    assert sb.state == "unknown" and "no BROKER-RECEIPTS.jsonl" in sb.basis
    real = Path.home() / "work" / "bh2" / "ops1" / "help-loop-20261104T2114Z"
    if real.is_dir():
        from pitwall.sources.receipts import ReceiptReader
        sb = {h.component: h for h in P.derive_path(ReceiptReader().read(str(real)))}["service_bus"]
        assert sb.state == "unknown"


def _walk(o, hits):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == "source" and isinstance(v, str):
                hits.append(v)
            _walk(v, hits)
    elif isinstance(o, list):
        for v in o:
            _walk(v, hits)


def test_demo_never_mixes_with_live():
    demo = Demo(FIX, load_corrections(CORR))
    ids = [s["id"] for s in demo.scenarios()]
    assert ids == ["idle", "active", "degraded", "recovered"]
    for sid in ids:
        snap, body = demo.snapshot(sid)
        d = json.loads(body)
        hits: list[str] = []
        _walk(d, hits)
        assert hits and all(h.startswith(f"demo:{sid}") for h in hits), [h for h in hits if not h.startswith("demo:")][:3]
        assert d["mode"] == "demo" and d["scenario"] == sid and "synthetic" in d["scenario_note"].lower()
        assert all(s["path"] == "fixture" for s in d["sources"])
        assert all(t["evidence_available"] is False for t in d["tasks"])
        assert not any("bh2/ops1" in json.dumps(t["path"]) for t in d["tasks"])
    degraded = json.loads(demo.snapshot("degraded")[1])
    assert "<img src=x onerror=alert(1)>" in degraded["tasks"][-1]["title"]

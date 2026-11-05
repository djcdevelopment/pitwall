"""Pure normalization: collector snapshots + receipt views -> one Snapshot (pitwall.v1).

Carries only fields it names. Fleet `command_summary` is never read. Null never becomes 0; a reading with
status ok and value 0.0 stays 0.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from . import participation as P
from .contract import (
    SCHEMA, ContextPack, Device, EngineCache, Exception_, Host, InspectionLink, JobCaches, Measurement,
    NetworkLink, Overall, Routing, Seat, Service, Snapshot, SourceRecord, Stage, Task, TokenUse,
)
from .corrections import apply_fraction
from .util import iso_from_epoch, loopback_url, parse_fraction, to_float, unknown

COVERAGE_CAP = "flow-top returns at most 10 tasks and has no CLI option to raise that limit; older tasks are not shown."
RESPONSIBILITY = {
    "hearth": "Model execution records, routing, artifacts, usage",
    "service_bus": "Command and notification transport",
    "ontology": "Definitions, mappings, semantic relationships; PostgreSQL-backed catalog",
    "duckdb": "Source snapshots and separately owned durable records",
    "lifetime_caches": "Context preparation and related routing capability; participation established per task",
    "aspire": "Trace inspection",
    "irc": "Operational observation delivery",
}
LINKS = {
    "aspire": ("Aspire traces", "http://127.0.0.1:18888"),
    "service_bus": ("Service Bus Explorer", "http://127.0.0.1:18080"),
    "ontology": ("Ontology catalog", "http://127.0.0.1:13000"),
}
HOST_ROLE = {"omen": "OMEN", "am4": "AM4", "fx99": "FX99"}
_PORT = re.compile(r":(\d{4,5})\b")
STAGES = [("request", "Request"), ("helper", "Helper"), ("parent_work", "Parent work"), ("checks", "Checks"), ("result", "Result")]


@dataclass
class Ctx:
    mode: str                       # live | demo
    scenario: Optional[str]
    read_at: str                    # ISO time Pitwall read the records
    corrections: list[dict] = field(default_factory=list)
    evidence_tasks: set[str] = field(default_factory=set)
    scenario_note: str = ""
    history_started_at: Optional[str] = None
    link_notes: dict[str, str] = field(default_factory=dict)

    def src(self, live: str) -> str:
        return f"demo:{self.scenario}" if self.mode == "demo" else live


# ---- fleet ---------------------------------------------------------------------------------------


def reading(r: Any, unit: str, ctx: Ctx, obs_iso: Optional[str], reachable: bool, scope: str = "device",
            src: str = "fleet-top") -> Measurement:
    """A fleet SensorReading -> Measurement. value None or status unavailable is never 0."""
    r = r if isinstance(r, dict) else {}
    val = to_float(r.get("value"))
    st = str(r.get("status", "unknown"))
    age = to_float(r.get("age_s"))
    note = str(r.get("note") or "")
    if val is None or st == "unavailable":
        status = "unreachable" if not reachable else "unknown"
        return Measurement(value=None, unit=unit, observed_at=obs_iso, read_at=ctx.read_at, source=ctx.src(src), status=status, scope=scope, note=note)  # type: ignore[arg-type]
    status = {"ok": "ok", "stale": "stale"}.get(st, "unknown")
    if status == "stale" and age is not None:
        note = (note + f" age {age:.1f}s").strip()
    return Measurement(value=val, unit=unit, observed_at=obs_iso, read_at=ctx.read_at, source=ctx.src(src), status=status, scope=scope, note=note)  # type: ignore[arg-type]


def plain(v: Any, unit: str, ctx: Ctx, obs_iso: Optional[str], reachable: bool, scope: str = "device") -> Measurement:
    val = to_float(v)
    if val is None:
        return Measurement(value=None, unit=unit, observed_at=obs_iso, read_at=ctx.read_at, source=ctx.src("fleet-top"),
                           status="unreachable" if not reachable else "unknown", scope=scope)  # type: ignore[arg-type]
    return Measurement(value=val, unit=unit, observed_at=obs_iso, read_at=ctx.read_at, source=ctx.src("fleet-top"),
                       status="ok" if reachable else "unreachable", scope=scope)  # type: ignore[arg-type]


def _ports(label: str) -> set[str]:
    return set(_PORT.findall(label or ""))


def norm_fleet(fleet: Optional[dict], fleet_state: str, ctx: Ctx) -> dict:
    """-> {hosts, devices, seats, engine_caches, notes, jobs}"""
    if not fleet:
        return {"hosts": [], "devices": [], "seats": [], "engine_caches": [], "notes": [], "slots": (0, 0)}
    ts = to_float(fleet.get("timestamp_epoch"))
    obs = iso_from_epoch(ts)
    endpoints = [e for e in fleet.get("endpoints", []) if isinstance(e, dict)]
    seat_eps = [e for e in endpoints if not str(e.get("endpoint_id", "")).endswith(":batch")]
    jobs = [j for j in fleet.get("active_jobs", []) if isinstance(j, dict)]
    job_targets = {j.get("target_device") for j in jobs}
    ep_by_key = {(e.get("host_id"), str(e.get("endpoint_id", "")).split(":")[-1]): e for e in seat_eps}

    devices: list[Device] = []
    for d in fleet.get("devices", []):
        if not isinstance(d, dict):
            continue
        reach = bool(d.get("reachable", False))
        stale = bool(d.get("is_stale", False))
        obs_d = iso_from_epoch(ts - (to_float(d.get("telemetry_age_s")) or 0.0)) if ts else obs
        util = reading(d.get("compute_util_pct"), "%", ctx, obs_d, reach)
        serving_active = any(
            (ep_by_key.get((d.get("host_id"), p)) or {}).get("active_reqs", 0) > 0 for p in _ports(str(d.get("workload_label", "")))
        ) if d.get("mode") == "serving" else False
        if not reach:
            state = "unreachable"
        elif stale:
            state = "stale"
        elif serving_active or (util.value is not None and util.value > 0) or d.get("device_id") in job_targets:
            state = "active"
        else:
            state = "idle"
        devices.append(Device(
            id=str(d.get("device_id")), host_id=str(d.get("host_id")), title=str(d.get("short_title", "")),
            hardware=str(d.get("hardware_identity", "")), mode=str(d.get("mode", "")), workload=str(d.get("workload_label", "")),
            owner=str(d.get("owner_label", "")), state=state,  # type: ignore[arg-type]
            utilization=util,
            memory_used=reading(d.get("vram_measured_used_gib"), "GiB", ctx, obs_d, reach),
            memory_total=plain(d.get("vram_measured_total_gib"), "GiB", ctx, obs_d, reach),
            power=reading(d.get("power_w"), "W", ctx, obs_d, reach),
            power_limit=plain(d.get("power_limit_w"), "W", ctx, obs_d, reach),
            temp_core=reading(d.get("temp_core_c"), "C", ctx, obs_d, reach),
            temp_mem=reading(d.get("temp_vram_c"), "C", ctx, obs_d, reach),
            link=str(d.get("link_info", "")),
        ))

    seats: list[Seat] = []
    cap_total = act_total = 0
    for e in seat_eps:
        eid = str(e.get("endpoint_id"))
        health = str(e.get("health", ""))
        up = health.upper() == "ONLINE"
        port = eid.split(":")[-1]
        dev_ids = [dv.id for dv in devices if dv.host_id == e.get("host_id") and port in _ports(dv.workload)]
        act, cap, q = to_float(e.get("active_reqs")), to_float(e.get("capacity_slots")), to_float(e.get("queued_reqs"))
        eobs = iso_from_epoch(ts - (to_float(e.get("age_s")) or 0.0)) if ts else obs
        base = dict(observed_at=eobs, read_at=ctx.read_at, source=ctx.src("fleet-top"), scope="host")
        if up and act is not None and cap is not None:
            occ = Measurement(value=act, unit="reqs", status="ok", numerator=act, denominator=cap, **base)  # type: ignore[arg-type]
            cap_total += int(cap)
            act_total += int(act)
        else:
            occ = Measurement(value=None, unit="reqs", status="unreachable" if not up else "unknown", numerator=None,
                              denominator=cap if cap is not None else None, **base)  # type: ignore[arg-type]
        queued = Measurement(value=q if up else None, unit="reqs", status="ok" if up and q is not None else ("unreachable" if not up else "unknown"), **base)  # type: ignore[arg-type]
        tps = to_float(e.get("tok_per_s"))
        gen = Measurement(value=tps if up else None, unit="tok/s", status="ok" if up and tps is not None else ("unreachable" if not up else "unknown"), **base)  # type: ignore[arg-type]
        if not up:
            state = "unreachable"
        elif fleet_state in ("stale", "unreachable"):
            state = "stale"
        elif act and act > 0:
            state = "active"
        else:
            state = "idle"
        cl = e.get("context_len")
        seats.append(Seat(id=eid, host_id=str(e.get("host_id")), label=str(e.get("label", eid)), model=str(e.get("model_id", "")),
                          state=state, health=health, occupancy=occ, queued=queued, generation_rate=gen,  # type: ignore[arg-type]
                          context_tokens=cl if isinstance(cl, int) and not isinstance(cl, bool) else None, device_ids=dev_ids))

    # engine counters
    engine: list[EngineCache] = []
    caches = fleet.get("caches") if isinstance(fleet.get("caches"), dict) else {}
    for c in caches.get("kv_prefix_caches", []) or []:
        if not isinstance(c, dict):
            continue
        hits, q = to_float(c.get("hits")), to_float(c.get("queries"))
        rate = to_float(c.get("hit_rate_pct"))
        online = bool(c.get("online", False))
        eid = str(c.get("endpoint_id"))
        engine.append(EngineCache(
            id=eid, label=f"{c.get('model_id', '')} KV prefix cache ({eid})",
            hit=Measurement(value=rate if online else None, unit="%", observed_at=obs, read_at=ctx.read_at, source=ctx.src("fleet-top"),
                            status=("ok" if rate is not None else "unknown") if online else "unreachable", scope="engine_lifetime",
                            window=str(c.get("time_window") or "engine uptime"), numerator=hits, denominator=q,
                            note=f"{int(hits) if hits is not None else '?'}/{int(q) if q is not None else '?'} {c.get('unit', 'tok')}"),  # type: ignore[arg-type]
        ))
    ast = caches.get("npu_ast_arena")
    if isinstance(ast, dict) and ast.get("online"):
        h, m = to_float(ast.get("hits")), to_float(ast.get("misses"))
        rate = to_float(ast.get("hit_rate_pct"))
        engine.append(EngineCache(
            id="npu_ast_arena", label=f"AST arena {ast.get('schema', '')} (:18097)",
            hit=Measurement(value=rate, unit="%", observed_at=obs, read_at=ctx.read_at, source=ctx.src("fleet-top"),
                            status="ok" if rate is not None else "unknown", scope="daemon_lifetime",
                            window=str(ast.get("time_window") or "daemon uptime"), numerator=h,
                            denominator=(h + m) if h is not None and m is not None else None,
                            note="daemon counters; not attributable to a job"),  # type: ignore[arg-type]
        ))

    # A retained reading from a stale or unreachable collector is stale, never "ok".
    if fleet_state in ("stale", "unreachable"):
        ms = [m for d in devices for m in (d.utilization, d.memory_used, d.memory_total, d.power, d.power_limit, d.temp_core, d.temp_mem)]
        ms += [m for s in seats for m in (s.occupancy, s.queued, s.generation_rate)] + [e.hit for e in engine]
        for m in ms:
            if m.status == "ok":
                m.status = "stale"
                m.note = (m.note + " retained from last good observation").strip()
        for d in devices:
            if d.state not in ("unreachable",):
                d.state = "stale"

    # hosts
    summ = fleet.get("summary") if isinstance(fleet.get("summary"), dict) else {}
    unreach_txt = " ".join(str(x) for x in (summ.get("unreachable_resources") or []))
    hosts: list[Host] = []
    for hid, lbl in (fleet.get("host_inventory") or {}).items():
        ds = [d for d in devices if d.host_id == hid]
        if (ds and all(d.state == "unreachable" for d in ds)) or (hid in unreach_txt.lower() and not ds):
            hs = "unreachable"
        elif fleet_state in ("stale", "unreachable"):
            hs = "stale"
        elif any(d.state == "active" for d in ds) or any(s.state == "active" for s in seats if s.host_id == hid):
            hs = "active"
        elif ds:
            hs = "idle"
        else:
            hs = "unknown"
        hosts.append(Host(id=str(hid), label=HOST_ROLE.get(str(hid), str(hid).upper()), role=str(lbl), state=hs))  # type: ignore[arg-type]
    notes = [str(x) for x in (fleet.get("known_blind_spots") or [])]
    return {"hosts": hosts, "devices": devices, "seats": seats, "engine_caches": engine, "notes": notes, "slots": (act_total, cap_total),
            "reason": str(summ.get("state_reason", ""))}


# ---- flow services -------------------------------------------------------------------------------


def norm_services(flow: Optional[dict], flow_state: str, ctx: Ctx, endpoint_rows: Optional[list[Service]] = None) -> list[Service]:
    rows = {s.get("service_id"): s for s in (flow or {}).get("services", []) if isinstance(s, dict)}
    order = [s.get("service_id") for s in (flow or {}).get("services", []) if isinstance(s, dict)] or \
        ["service_bus", "ontology", "hearth", "lifetime_caches", "duckdb", "aspire"]
    out: list[Service] = list(endpoint_rows or [])
    for sid in order:
        s = rows.get(sid, {})
        if endpoint_rows is not None and sid == "service_bus":
            continue  # flow-top combines Explorer and :5672; Pitwall reports each instance itself
        if endpoint_rows is not None and sid == "aspire":
            out.append(_irc_row(ctx))
            continue
        raw = str(s.get("state", "unknown"))
        state = {"idle": "idle", "active": "active", "unavailable": "unreachable", "stale": "stale"}.get(raw, "unknown")
        if flow is None:
            state = "unknown"
        elif flow_state == "stale" and state not in ("unreachable",):
            state = "stale"
        link = None
        if sid in LINKS:
            lbl, url = LINKS[sid]
            link = InspectionLink(label=lbl, url=url, service_id=sid, enabled=state != "unreachable",
                                  reason=f"{s.get('name', sid)} unreachable at last probe ({s.get('detail', '')})" if state == "unreachable" else "")
        out.append(Service(
            id=str(sid), name=str(s.get("name", sid)), responsibility=RESPONSIBILITY.get(str(sid), ""),
            endpoint=str(s.get("host_endpoint", "")), state=state,  # type: ignore[arg-type]
            detail=str(s.get("detail", "")), source=ctx.src(str(s.get("source", "flow-top"))), age_s=to_float(s.get("obs_age_s")), link=link,
        ))
        if sid == "aspire":
            out.append(_irc_row(ctx))
    return out


def _irc_row(ctx: Ctx) -> Service:
    return Service(
        id="irc", name="IRC (passive receipts)", responsibility=RESPONSIBILITY["irc"], endpoint="IRC-RECEIPTS.jsonl in run directories",
        state="unknown", detail="Not probed: flow-top follows a zero-socket rule for IRC. Per-task delivery is read from receipts.",
        source=ctx.src("flow-top aspire row (zero IRC socket connects)"), age_s=None, link=None,
    )


# ---- tasks ----------------------------------------------------------------------------------------

_STAGE_STATE = {"done": "done", "working": "working", "waiting": "waiting", "attention": "attention", "failed": "failed", "unused": "unused"}


def _opt_int(v: Any) -> Optional[int]:
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def build_task(ft: dict, view: P.ReceiptView, services: dict[str, str], ctx: Ctx) -> Task:
    tid = str(ft.get("task_id"))
    src = lambda name: ctx.src(f"receipts:{name}")  # noqa: E731
    irc_status = str(ft.get("irc_delivery_status", ""))
    outcome = P.derive_outcome(view, flow_label=str(ft.get("outcome_label", "")), flow_state=str(ft.get("state", "")),
                               irc_status=irc_status, recorded_text=str(ft.get("outcome") or ""),
                               last_progress_utc=str(ft.get("last_progress_utc") or ""))
    active = outcome.state == "active"
    path = P.derive_path(view, task_active=active, irc_status=irc_status)
    checks = P.derive_checks(view, ft.get("checks_passed") if isinstance(ft.get("checks_passed"), bool) else None)
    review = P.derive_review(view, str(ft.get("review_status", "")))
    delivery = P.derive_delivery(view, irc_status, str(ft.get("irc_delivery_label", "")))

    ribbon = ft.get("stage_ribbon") if isinstance(ft.get("stage_ribbon"), dict) else {}
    stages: list[Stage] = []
    for sid, lbl in STAGES:
        st = _STAGE_STATE.get(str(ribbon.get(sid, "")), "unknown")
        if sid == "checks":
            st = {"passed": "done", "failed": "failed", "unknown": "unknown"}[checks.state]
        elif sid == "result":
            st = {"completed": "done", "recovered": "done", "active": "working", "staged": "waiting", "failed": "failed"}.get(outcome.state, "unknown")
        stages.append(Stage(id=sid, label=lbl, state=st))  # type: ignore[arg-type]

    hp = P.hearth_provider(view)
    routing = Routing(
        task_family=str(hp.get("task_family") or ft.get("task_family") or ""), provider=str(hp.get("provider") or ft.get("hearth_provider") or ""),
        model=str(hp.get("model") or ft.get("hearth_model") or ""), routed_by=str(hp.get("routed_by") or ft.get("selected_route") or ""),
        regime=str(ft.get("regime_summary") or ""), job_id=str(hp.get("job_id") or ft.get("hearth_job_id") or ""))
    tokens = TokenUse(
        model_calls=_opt_int(ft.get("model_calls")), tokens_in=_opt_int(ft.get("tokens_in_total")), tokens_out=_opt_int(ft.get("tokens_out_total")),
        tokens_reasoning=_opt_int(ft.get("tokens_reasoning_total")), budget_in=_opt_int(ft.get("budget_tokens_in")),
        budget_out=_opt_int(ft.get("budget_tokens_out")), budget_calls=_opt_int(ft.get("budget_calls")), emit_repairs=_opt_int(ft.get("hearth_emit_repairs")))

    # context: two different packs, labelled separately
    res = view.js("RESULT.json")
    metrics = res.get("metrics") if isinstance(res.get("metrics"), dict) else {}
    cd = view.js("CONTEXT-DELIVERY.json")
    pk = to_float(ft.get("pack_size_bytes"))
    hearth_input = Measurement(value=pk, unit="B", read_at=ctx.read_at, source=ctx.src("flow-top pack_size_bytes"), scope="job",
                               status="ok" if pk is not None else "unknown", note="HEARTH input artifact, not the ontology context pack")
    sel_size = view.files.get("SELECTED-CONTEXT-PACK.json")
    sel_from = "SELECTED-CONTEXT-PACK.json size"
    if sel_size is None and to_float(metrics.get("selected_context_pack_bytes")) is not None:
        sel_size, sel_from = to_float(metrics.get("selected_context_pack_bytes")), "RESULT.json metrics.selected_context_pack_bytes"
    selected = Measurement(value=sel_size, unit="B", read_at=ctx.read_at, source=src(sel_from.split(" ")[0]) if sel_size is not None else ctx.src("receipts"),
                           scope="job", status="ok" if sel_size is not None else "unknown",
                           note=f"selected ontology context pack ({sel_from})" if sel_size is not None else "No selected context pack recorded for this task.")

    def facts(key: str, label: str) -> Measurement:
        fr = parse_fraction(metrics.get(key))
        if not fr:
            return unknown("facts", ctx.src("receipts"), ctx.read_at, f"No {label} required-facts figure recorded.")
        return Measurement(value=f"{fr[0]}/{fr[1]}", unit="facts", read_at=ctx.read_at, source=src("RESULT.json"), status="ok", scope="job",
                           numerator=fr[0], denominator=fr[1], note=f"RESULT.json metrics.{key}")

    f_sel = facts("required_facts_covered_selected", "selected")
    f_base, corr = apply_fraction(ctx.corrections, tid, "required_facts_baseline", facts("required_facts_covered_baseline", "baseline"), ctx.read_at) if ctx.mode == "live" \
        else (facts("required_facts_covered_baseline", "baseline"), [])
    cls = metrics.get("comparison_classification_vs_baseline")
    context = ContextPack(concept=str(cd.get("requested_concept") or ""), hearth_input=hearth_input, selected_pack=selected,
                          selected_pack_sha256=str(cd.get("context_sha256") or ""), required_facts_selected=f_sel, required_facts_baseline=f_base,
                          comparison_note=(f"RESULT.json classification: {cls}" if cls else ""), corrections=corr)

    # caches: four separate things; engine counters live elsewhere
    cached = to_float(ft.get("cached_input_tokens"))
    kv_note = str(ft.get("cached_input_tokens_note") or "") or "Model KV cache hit is not recorded in the job's receipts."
    caches = JobCaches(
        pack_cache=P.derive_pack_cache(view, ctx.read_at, src("PACK-CACHE-RECEIPTS.json")),
        ast_ram=unknown("hit", ctx.src("receipts"), ctx.read_at, "No job receipt attributes AST/RAM cache lookups to this task; engine daemon counters are shown separately."),
        model_kv=(Measurement(value=cached, unit="tok", read_at=ctx.read_at, source=ctx.src("flow-top cached_input_tokens"), status="ok", scope="job", note="cached input tokens")
                  if cached is not None else unknown("tok", ctx.src("flow-top cached_input_tokens_note"), ctx.read_at, kv_note)),
    )

    # links
    links: list[InspectionLink] = []
    used = {h.component: h.state for h in path}

    def link(label: str, url: Any, service_id: str) -> None:
        u = loopback_url(url)
        if not u:
            return
        st = services.get(service_id, "unknown")
        links.append(InspectionLink(label=label, url=u, service_id=service_id, enabled=st != "unreachable",
                                    reason=f"{service_id.replace('_', ' ')} unreachable at last probe" if st == "unreachable" else "",
                                    annotation=ctx.link_notes.get(service_id, "")))

    link("Aspire trace", ft.get("aspire_trace_url"), "aspire")
    link("Service Bus Explorer", ft.get("broker_explorer_url"), "service_bus")
    if used.get("ontology") in ("used", "active"):
        link("Ontology entry", ft.get("ontology_entry_url"), "ontology")
    link("Preview", ft.get("preview_url"), "preview")

    elapsed = to_float(ft.get("elapsed_s"))
    durations = P.derive_durations(view, elapsed, to_float(ft.get("helper_elapsed_s")), _opt_int(ft.get("features_completed")))
    attention = str(ft.get("attention_summary") or "")
    if attention.lower().startswith("none"):
        attention = ""
    return Task(
        id=tid, title=str(ft.get("title", tid)), short_title=str(ft.get("human_title") or ft.get("title") or tid), actor=str(ft.get("actor", "")),
        host=str(ft.get("host", "")), stage=str(ft.get("stage", "")), stages=stages, latest_progress=str(ft.get("last_progress", "")),
        latest_progress_at=str(ft.get("last_progress_utc") or "") or None, outcome=outcome, checks=checks, review=review, delivery=delivery,
        attention=attention, durations=durations, tokens=tokens, routing=routing, path=path, context=context, caches=caches,
        duckdb=P.derive_duckdb_steps(view), artifacts=P.derive_artifacts(view), links=links,
        evidence_available=(ctx.mode == "live" and tid in ctx.evidence_tasks),
    )


# ---- snapshot --------------------------------------------------------------------------------------


def build_snapshot(*, ctx: Ctx, generated_at: str, fleet: Optional[dict], flow: Optional[dict], fleet_rec: SourceRecord,
                   flow_rec: SourceRecord, receipts_rec: SourceRecord, views: dict[str, P.ReceiptView],
                   endpoint_rows: Optional[list[Service]] = None, endpoint_links: Optional[dict] = None,
                   endpoints_rec: Optional[SourceRecord] = None) -> Snapshot:
    fl = norm_fleet(fleet, fleet_rec.state, ctx)
    services = norm_services(flow, flow_rec.state, ctx, endpoint_rows)
    svc_state = {s.id: s.state for s in services}
    svc_state["preview"] = "unknown"
    for key, (state, note) in (endpoint_links or {}).items():
        svc_state[key] = state
        if note:
            ctx.link_notes[key] = note
    tasks: list[Task] = []
    flow_tasks = [t for t in (flow or {}).get("tasks", []) if isinstance(t, dict)][:10]
    for ft in flow_tasks:
        tid = str(ft.get("task_id"))
        tasks.append(build_task(ft, views.get(tid) or P.ReceiptView(run_dir=str(ft.get("run_dir") or "")), svc_state, ctx))

    default = next((t.id for t in tasks if t.outcome.state == "active"), tasks[0].id if tasks else None)

    # exception priority: failed active task > collector unreachable > collector stale > current service unreachable
    exc: Optional[Exception_] = None
    bad = next((t for t in tasks if t.outcome.state == "active" and (t.checks.state == "failed" or any(s.state == "failed" for s in t.stages))), None)
    recs = [fleet_rec, flow_rec]
    if bad:
        exc = Exception_(level="failed", text=f"Active task failing: {bad.short_title}", source=ctx.src("receipts"))
    elif any(r.state == "unreachable" for r in recs):
        r = next(r for r in recs if r.state == "unreachable")
        exc = Exception_(level="unreachable", text=f"{r.label} collector unreachable" + (f": {r.last_error}" if r.last_error else ""), source=ctx.src(r.label))
    elif any(r.state == "stale" for r in recs):
        r = next(r for r in recs if r.state == "stale")
        exc = Exception_(level="stale", text=f"{r.label} collector stale (last observation older than {r.stale_after_s:.0f}s)", source=ctx.src(r.label))
    else:
        down = [s for s in services if s.state == "unreachable"]
        if down:
            s, more = down[0], f"; {len(down) - 1} more below" if len(down) > 1 else ""
            first = s.detail.split(". ")[0].rstrip(".")
            exc = Exception_(level="service", text=f"{s.name} unreachable: {first}{more}", source=ctx.src(s.source or "flow-top"))

    act_slots, cap_slots = fl["slots"]
    any_task = any(t.outcome.state == "active" for t in tasks)
    if any(r.state == "unreachable" for r in recs):
        ostate = "unreachable"
    elif any(r.state == "stale" for r in recs):
        ostate = "stale"
    elif any_task or act_slots > 0:
        ostate = "active"
    else:
        ostate = "idle"
    n_act = sum(1 for t in tasks if t.outcome.state == "active")
    reason = f"{n_act} active task(s); {act_slots}/{cap_slots} seat slots occupied" + (f"; fleet-top: {fl['reason']}" if fl.get("reason") else "")
    overall = Overall(state=ostate, headline={"active": "Active", "idle": "Idle", "stale": "Stale data", "unreachable": "Collector unreachable"}[ostate], reason=reason)  # type: ignore[arg-type]

    notes = [COVERAGE_CAP, *fl["notes"]]
    if flow:
        if isinstance(flow.get("duckdb"), dict) and flow["duckdb"].get("updates_deletions_status"):
            notes.append("DuckDB row updates and deletions: " + str(flow["duckdb"]["updates_deletions_status"]))
        if flow.get("headline_available") and endpoint_rows is None:
            notes.append(str(flow["headline_available"]))
    if endpoint_rows is not None:
        notes.append("Broker, Explorer and Aspire rows are Pitwall's own observations. flow-top combines Explorer and :5672 into one row and reports backlog 0 when discovery fails, so that row is not used.")
    notes.append("flow-top does not probe IRC (zero-socket rule); IRC state is read per task from receipts.")
    notes.append("Task path states are derived from run-directory receipts; flow-top's not_used_by_job labels are not used.")

    network = [NetworkLink(id="omen-am4", label="OMEN-AM4 link latency", latency=Measurement(
        value=None, unit="ms", read_at=ctx.read_at, source=ctx.src("fleet-top known_blind_spots"), status="unknown", scope="host",
        note="unmeasured: fleet-top lists this as a known blind spot"))]
    return Snapshot(
        schema=SCHEMA, seq=0, mode=ctx.mode, scenario=ctx.scenario, scenario_note=ctx.scenario_note,  # type: ignore[call-arg]
        generated_at=generated_at, overall=overall, exception=exc, sources=[fleet_rec, flow_rec, receipts_rec] + ([endpoints_rec] if endpoints_rec else []), hosts=fl["hosts"],
        devices=fl["devices"], seats=fl["seats"], services=services, engine_caches=fl["engine_caches"], network=network, tasks=tasks,
        default_task_id=default, coverage_notes=notes, history_started_at=ctx.history_started_at,
    )

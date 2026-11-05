"""Pure derivation of what a task touched, from its receipts.

Input is a ReceiptView: which files are present plus parsed contents. No file or network access happens
here, so demo mode can hand in a synthetic view. flow-top's `state` and `not_used_by_job` are never read.

Rules (see the plan, "Participation rules"): a component is `used` only when a named receipt says so;
`unused` only when a receipt states non-use (today only JEPA file packing, `desired.packed_files == []`);
otherwise `unknown`. Absence of a receipt alone is never `unused`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .contract import (
    ArtifactRef,
    Checks,
    Delivery,
    DuckDbSteps,
    Measurement,
    Outcome,
    PathHop,
    Review,
    ScopedDuration,
)
from .util import parse_iso, scrub_identifiers, to_float

CANON = ["service_bus", "hearth", "steppewise", "ontology", "jepa", "ast_cache", "duckdb", "irc", "parent"]
LABELS = {
    "service_bus": "Service Bus",
    "hearth": "HEARTH",
    "steppewise": "Steppewise / MAF",
    "ontology": "Ontology",
    "jepa": "JEPA",
    "ast_cache": "AST/RAM cache",
    "duckdb": "DuckDB",
    "irc": "IRC",
    "parent": "Parent",
}
_TERMINAL = {"succeeded", "failed", "cancelled", "canceled", "completed", "error", "expired"}
_BROKER_DONE = {"completed", "abandoned", "dead_lettered", "deadlettered"}
_NUM_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine"}


@dataclass
class ReceiptView:
    run_dir: str = ""
    files: dict[str, int] = field(default_factory=dict)       # top-level regular files: name -> bytes
    dirs: set[str] = field(default_factory=set)
    data: dict[str, Any] = field(default_factory=dict)        # parsed .json receipts by name
    lines: dict[str, list[dict]] = field(default_factory=dict)  # parsed .jsonl receipts by name
    record_ids: dict[str, str] = field(default_factory=dict)  # file name -> servable evidence record id
    synthetic: bool = False                                   # demo: built from fixture fields, not files
    label: str = ""

    def has(self, name: str) -> bool:
        return name in self.files or name in self.data or name in self.lines

    def js(self, name: str) -> dict:
        v = self.data.get(name)
        return v if isinstance(v, dict) else {}

    def jl(self, name: str) -> list[dict]:
        return self.lines.get(name) or []

    def rid(self, name: str) -> Optional[str]:
        return self.record_ids.get(name)


def _sfx(view: ReceiptView) -> str:
    return " [demo: synthesized from fixture fields]" if view.synthetic else ""


def _host_from_provider(provider: str, node: str = "") -> Optional[str]:
    for s in (node, provider):
        s = (s or "").lower()
        for h in ("omen", "am4", "fx99"):
            if s.startswith(h):
                return h
    return None


def _exec_doc(view: ReceiptView) -> tuple[str, dict]:
    for name in ("execution.json", "job-succeeded.json"):
        d = view.js(name)
        if d:
            return name, d
    return "", {}


def hearth_provider(view: ReceiptView) -> dict:
    name, d = _exec_doc(view)
    if not d:
        return {}
    inv = (d.get("invocations") or [{}])[0] if isinstance(d.get("invocations"), list) else {}
    cap = d.get("capability") if isinstance(d.get("capability"), dict) else {}
    return {
        "file": name,
        "provider": d.get("provider") or "",
        "model": d.get("model") or "",
        "job_id": d.get("job_id") or "",
        "routed_by": d.get("routed_by") or "",
        "task_family": d.get("task_family") or "",
        "status": d.get("status") or "",
        "node": cap.get("node") or (inv.get("capability") or {}).get("node") or "",
        "started_at": inv.get("started_at") or d.get("created_at") or "",
    }


def _hop(view, comp, state, summary, basis, host=None, rec=None, at=None, label=None) -> PathHop:
    return PathHop(
        component=comp,
        label=label or LABELS[comp],
        state=state,
        host_id=host,
        summary=summary,
        basis=basis + _sfx(view),
        evidence_record=rec,
        observed_at=at or None,
    )


def _unknown(view, comp, summary, basis, host=None) -> PathHop:
    return PathHop(component=comp, label=LABELS[comp], state="unknown", host_id=host, summary=summary, basis=basis)


def _packed_files(view: ReceiptView) -> tuple[Optional[list], str]:
    """(packed_files, receipt name) from the first receipt that carries desired.packed_files. Non-empty wins."""
    found: tuple[Optional[list], str] = (None, "")
    for name in ("execution.json", "submitted.json", "job-succeeded.json"):
        desired = view.js(name).get("desired")
        pf = desired.get("packed_files") if isinstance(desired, dict) else None
        if isinstance(pf, list):
            if pf:
                return pf, name
            if found[0] is None:
                found = (pf, name)
    return found


def duckdb_facts(view: ReceiptView) -> dict:
    pcr = view.js("PACK-CACHE-RECEIPTS.json")
    cold = pcr.get("cold_receipt") if isinstance(pcr.get("cold_receipt"), dict) else {}
    q = to_float(cold.get("duckdb_queries"))
    rec = view.js("DUCKDB-RECEIPT.json")
    tables = rec.get("tables") if isinstance(rec.get("tables"), dict) else {}
    rows = {k: v.get("row_count") for k, v in tables.items() if isinstance(v, dict) and to_float(v.get("row_count")) is not None}
    rb = rec.get("read_back_verified")
    return {"queries": q, "rec": rec, "rows": rows, "read_back": rb if isinstance(rb, bool) else None, "has_pcr": bool(pcr)}


def derive_path(view: ReceiptView, task_active: bool = False, irc_status: str = "") -> list[PathHop]:
    hops: list[PathHop] = []

    # Service Bus: never `unused`.
    br = view.jl("BROKER-RECEIPTS.jsonl")
    if br:
        kinds = [str(e.get("kind", "?")) for e in br]
        seq = next((e.get("sequence_number") for e in reversed(br) if e.get("sequence_number") is not None), None)
        dc = next((e.get("delivery_count") for e in reversed(br) if e.get("delivery_count") is not None), None)
        queue = next((e.get("queue") for e in br if e.get("queue")), "")
        active = task_active and not any(k in _BROKER_DONE for k in kinds)
        hops.append(_hop(view, "service_bus", "active" if active else "used",
                         f"queue {queue}; seq {seq}; delivery_count {dc}; receipts: {', '.join(kinds)}",
                         f"BROKER-RECEIPTS.jsonl ({len(br)} entries)", "omen", view.rid("BROKER-RECEIPTS.jsonl"), br[0].get("at")))
    else:
        hops.append(_unknown(view, "service_bus", "Not recorded. A missing broker receipt does not establish direct submission.",
                             "no BROKER-RECEIPTS.jsonl in run directory", "omen"))

    # HEARTH
    hp = hearth_provider(view)
    if hp:
        host = _host_from_provider(hp["provider"], hp["node"]) or "omen"
        active = task_active and str(hp["status"]).lower() not in _TERMINAL
        hops.append(_hop(view, "hearth", "active" if active else "used",
                         f"{hp['provider']} ({hp['model']}), job {str(hp['job_id'])[:20]}, status {hp['status']}",
                         f"{hp['file']}: provider, model, job_id, status", host, view.rid(hp["file"]), hp["started_at"]))
    else:
        run = next((n for n in ("job-running.json", "job-queued.json", "submitted.json") if view.js(n)), "")
        if run:
            d = view.js(run)
            st = str(d.get("status", "")) or "submitted"
            host = _host_from_provider(str(d.get("provider", ""))) or "omen"
            hops.append(_hop(view, "hearth", "active" if task_active and st.lower() not in _TERMINAL else "used",
                             f"{d.get('provider', '')} job {str(d.get('job_id', ''))[:20]}, status {st}",
                             f"{run}: provider, job_id, status", host, view.rid(run), d.get("created_at")))
        else:
            hops.append(_unknown(view, "hearth", "No HEARTH job receipt recorded.", "no execution.json or job-succeeded.json in run directory", "omen"))

    # Steppewise / MAF
    lm = view.js("LOOKUP-MEASURE.json")
    if lm:
        dur = to_float(lm.get("duration_ms"))
        hops.append(_hop(view, "steppewise", "used",
                         f"reviewed lookup{f' in {dur:.0f} ms' if dur is not None else ''}; {lm.get('execution', '')}".strip(),
                         "LOOKUP-MEASURE.json", "omen", view.rid("LOOKUP-MEASURE.json"), lm.get("started_at")))
    elif "lookup-state" in view.dirs:
        hops.append(_hop(view, "steppewise", "used", "lookup events recorded", "lookup-state/ events directory", "omen"))
    else:
        hops.append(_unknown(view, "steppewise", "No lookup receipt recorded.", "no LOOKUP-MEASURE.json or lookup events in run directory", "omen"))

    # Ontology (catalog on AM4)
    cd = view.js("CONTEXT-DELIVERY.json")
    if cd or view.has("DELIVERED-DEFINITION.json"):
        concept = cd.get("requested_concept") if cd else ""
        src = "CONTEXT-DELIVERY.json" if cd else "DELIVERED-DEFINITION.json"
        names = [n for n in ("DELIVERED-DEFINITION.json", "CONTEXT-DELIVERY.json") if view.has(n)]
        hops.append(_hop(view, "ontology", "used",
                         f"delivered: {concept}" if concept else "definition delivered into the helper prompt",
                         " + ".join(names) if names else src, "am4", view.rid(src), lm.get("started_at") if lm else None))
    else:
        hops.append(_unknown(view, "ontology", "No ontology delivery recorded.", "no DELIVERED-DEFINITION.json or CONTEXT-DELIVERY.json in run directory", "am4"))

    # JEPA, HEARTH file packing only
    pf, pf_name = _packed_files(view)
    if pf is None:
        hops.append(_unknown(view, "jepa", "No receipt records HEARTH file packing.", "no desired.packed_files in execution.json, submitted.json or job-succeeded.json", "omen"))
    elif pf:
        hops.append(_hop(view, "jepa", "used", f"{len(pf)} packed file(s) for HEARTH file packing", f"desired.packed_files non-empty ({pf_name})", "omen", view.rid(pf_name)))
    else:
        hops.append(PathHop(component="jepa", label="JEPA: not used for HEARTH file packing", state="unused", host_id="omen",
                            summary="not used for HEARTH file packing",
                            basis=f"desired.packed_files=[] ({pf_name})" + _sfx(view), evidence_record=view.rid(pf_name)))

    # AST/RAM cache: only an attributed job receipt could establish this; none of today's receipts does.
    hops.append(_unknown(view, "ast_cache", "Not attributed to this task by any receipt.", "no job receipt attributes AST arena lookups to this task", "omen"))

    # DuckDB
    df = duckdb_facts(view)
    if df["rec"] or (df["queries"] is not None and df["queries"] > 0):
        bits, basis = [], []
        if df["queries"] is not None and df["queries"] > 0:
            bits.append(f"source snapshot read ({int(df['queries'])} queries)")
            basis.append("PACK-CACHE-RECEIPTS.json cold_receipt.duckdb_queries")
        if df["rows"]:
            bits.append("transition written")
            basis.append("DUCKDB-RECEIPT.json tables")
        if df["read_back"]:
            bits.append("read back verified")
            basis.append("DUCKDB-RECEIPT.json read_back_verified")
        rd = str(view.run_dir)
        on_omen = bool(rd and (rd.startswith(str(Path.home())) or rd.startswith("~/") or rd.startswith("/home/")))
        hops.append(_hop(view, "duckdb", "used", "; ".join(bits) or "DuckDB receipt present", "; ".join(basis) or "DUCKDB-RECEIPT.json",
                         "omen" if on_omen else None, view.rid("DUCKDB-RECEIPT.json"), df["rec"].get("recorded_at") if df["rec"] else None))
    else:
        hops.append(_unknown(view, "duckdb", "No DuckDB receipt recorded.", "no DUCKDB-RECEIPT.json and no duckdb_queries in pack receipts", None))

    # IRC
    irc = view.jl("IRC-RECEIPTS.jsonl")
    if irc:
        rec = irc_status == "recovered" or bool(view.js("RECOVERY.json"))
        hops.append(_hop(view, "irc", "used", f"{len(irc)} IRC receipts" + ("; delivery recovered once or more" if rec else ""),
                         f"IRC-RECEIPTS.jsonl ({len(irc)} entries)", "omen", view.rid("IRC-RECEIPTS.jsonl"), irc[0].get("at")))
    else:
        hops.append(_unknown(view, "irc", "No IRC receipt recorded.", "no IRC-RECEIPTS.jsonl in run directory", "omen"))

    # Parent
    cons = view.js("consumption.json")
    if cons:
        hops.append(_hop(view, "parent", "used", f"consumed by {cons.get('parent', '?')}; independent_review={cons.get('independent_review', 'not recorded')}",
                         "consumption.json", "omen", view.rid("consumption.json"), cons.get("at")))
    else:
        hops.append(_unknown(view, "parent", "No parent consumption recorded.", "no consumption.json in run directory", "omen"))

    return _order(hops)


def _order(hops: list[PathHop]) -> list[PathHop]:
    """Observed timeline when receipts give timestamps; hops without one follow in a stable order."""
    idx = {c: i for i, c in enumerate(CANON)}
    timed = [(parse_iso(h.observed_at), idx[h.component], h) for h in hops]
    with_t = sorted([t for t in timed if t[0] is not None], key=lambda t: (t[0], t[1]))
    without = sorted([t for t in timed if t[0] is None], key=lambda t: t[1])
    return [t[2] for t in with_t + without]


# ---- outcome, checks, review, delivery ---------------------------------------------------------


def _result_present(view: ReceiptView) -> Optional[str]:
    for n in ("RESULT.json", "consumption.json", "SUMMARY.json"):
        if view.has(n):
            return n
    return None


def recovery_recorded(view: ReceiptView, irc_status: str) -> bool:
    rec = view.js("RECOVERY.json")
    n = to_float(rec.get("application_recoveries")) if rec else None
    return bool((n is not None and n > 0) or irc_status == "recovered")


def derive_outcome(view: ReceiptView, *, flow_label: str, flow_state: str, irc_status: str,
                   recorded_text: str, last_progress_utc: str = "") -> Outcome:
    cons = view.js("consumption.json")
    text = scrub_identifiers((cons.get("action") if isinstance(cons.get("action"), str) and cons.get("action") else recorded_text) or "")
    label, state = (flow_label or "").lower(), (flow_state or "").lower()
    res = view.js("RESULT.json")
    finished = res.get("completed_at") or res.get("finished_at") or cons.get("at") or (last_progress_utc or None)
    if state == "staged" or label == "staged":
        return Outcome(state="staged", label="Staged", summary=text, finished_at=None)
    if state == "active" or label in ("working", "active"):
        return Outcome(state="active", label="Active", summary=text, finished_at=None)
    if label == "failed":
        return Outcome(state="failed", label="Failed", summary=text, finished_at=finished)
    if label == "completed":
        present = _result_present(view)
        if not present:
            return Outcome(state="unknown", label="Completion not evidenced",
                           summary="flow-top reports completed; no RESULT.json, consumption.json or equivalent in the run directory.", finished_at=None)
        if recovery_recorded(view, irc_status):
            return Outcome(state="recovered", label="Completed with recovery", summary=text, finished_at=finished)
        return Outcome(state="completed", label="Completed", summary=text, finished_at=finished)
    return Outcome(state="unknown", label="Outcome not recorded", summary=text, finished_at=None)


def derive_checks(view: ReceiptView, flow_checks_passed: Optional[bool]) -> Checks:
    pc = view.js("PARENT-CHECKS.json")
    if isinstance(pc.get("passed"), bool):
        n = sum(1 for k, v in pc.items() if isinstance(v, bool) and k != "passed")
        return Checks(state="passed" if pc["passed"] else "failed",
                      detail=f"PARENT-CHECKS.json passed={str(pc['passed']).lower()}" + (f" ({n} boolean fields)" if n else "") + _sfx(view),
                      evidence_record=view.rid("PARENT-CHECKS.json"))
    ck = view.js("CHECKS.json").get("checks")
    if isinstance(ck, list) and ck and all(isinstance(c, dict) and isinstance(c.get("passed"), bool) for c in ck):
        ok = sum(1 for c in ck if c["passed"])
        return Checks(state="passed" if ok == len(ck) else "failed", detail=f"CHECKS.json: {ok} of {len(ck)} checks passed",
                      evidence_record=view.rid("CHECKS.json"))
    # flow-top sets checks_passed=True and review_status="review pending" as constants for any
    # completed task (collectors.py:1130-1131, 1738-1739), so neither is evidence. Only a recorded
    # failure from it is carried; a pass needs a receipt.
    cons = view.js("consumption.json")
    if cons.get("check_evidence"):
        name = str(cons["check_evidence"]).rsplit("/", 1)[-1]
        return Checks(state="passed", detail=f"Parent attestation in consumption.json; check evidence {name}. No separate pass/fail field.",
                      evidence_record=view.rid(name) or view.rid("consumption.json"))
    if flow_checks_passed is False:
        return Checks(state="failed", detail="checks_passed=false (flow-top; no check receipt read)" + _sfx(view))
    return Checks(state="unknown", detail="No check receipt with a recorded result.")


def derive_review(view: ReceiptView, flow_review_status: str) -> Review:
    cons = view.js("consumption.json")
    v, src, rid = str(cons.get("independent_review", "")).strip().lower(), "consumption.json independent_review", view.rid("consumption.json")
    if not v:
        v, src, rid = str(view.js("REVIEW-BUNDLE.json").get("independent_adoption_review", "")).strip().lower(), "REVIEW-BUNDLE.json independent_adoption_review", view.rid("REVIEW-BUNDLE.json")
    if not v:
        return Review(state="unknown", detail="No review state in a receipt.")
    detail = f"{src}={v}" + _sfx(view)
    if "pending" in v:
        return Review(state="pending", detail=detail, evidence_record=rid)
    if v.startswith("accept"):
        return Review(state="accepted", detail=detail, evidence_record=rid)
    if v.startswith("reject"):
        return Review(state="rejected", detail=detail, evidence_record=rid)
    return Review(state="unknown", detail=detail, evidence_record=rid)


def derive_delivery(view: ReceiptView, irc_status: str, irc_label: str) -> Delivery:
    rid = view.rid("IRC-RECEIPTS.jsonl")
    st = (irc_status or "").lower()
    if recovery_recorded(view, st):
        return Delivery(state="recovered", label=irc_label or "recovered", evidence_record=rid)
    m = {"delivered": "delivered", "active": "active", "waiting": "waiting", "failed": "failed"}
    if st in ("active", "waiting", "failed"):
        return Delivery(state=m[st], label=irc_label or st, evidence_record=rid)  # type: ignore[arg-type]
    if st == "delivered" and view.has("IRC-RECEIPTS.jsonl"):
        return Delivery(state="delivered", label=irc_label or st, evidence_record=rid)
    return Delivery(state="unknown", label="no IRC receipt in run directory", evidence_record=rid)


# ---- durations, caches, duckdb ------------------------------------------------------------------


def derive_durations(view: ReceiptView, flow_elapsed_s: Optional[float], flow_helper_s: Optional[float],
                     features_completed: Optional[int]) -> list[ScopedDuration]:
    out: list[ScopedDuration] = []
    res = view.js("RESULT.json")
    metrics = res.get("metrics") if isinstance(res.get("metrics"), dict) else {}
    wall = to_float(res.get("wall_seconds"))
    if wall is not None:
        n = features_completed or 0
        if n > 1:
            w = _NUM_WORDS.get(n, str(n))
            scope = f"one {w}-feature batch, freeze through confirmed receipt; not {w} independent throughput measurements"
        else:
            scope = str(res.get("boundary") or "RESULT.json wall_seconds")
        out.append(ScopedDuration(label="Wall time (RESULT.json)", seconds=wall, scope_note=scope))
    bs = to_float(metrics.get("broker_send_to_parent_consume_elapsed_s"))
    if bs is not None:
        out.append(ScopedDuration(label="Broker send to parent consume", seconds=bs,
                                  scope_note="broker_send_to_parent_consume_elapsed_s (RESULT.json): BROKER-RECEIPTS send to consumption.json"))
    gen_ms = to_float(metrics.get("hearth_generation_ms"))
    if gen_ms is not None:
        out.append(ScopedDuration(label="Helper generation", seconds=round(gen_ms / 1000.0, 2),
                                  scope_note="HEARTH generation across all model calls (RESULT.json hearth_generation_ms)"))
    elif flow_helper_s is not None:
        out.append(ScopedDuration(label="Helper generation", seconds=flow_helper_s, scope_note="helper generation (flow-top helper_elapsed_s)"))
    if flow_elapsed_s is not None and not (wall is not None and abs(wall - flow_elapsed_s) < 1.5):
        out.append(ScopedDuration(label="First to last receipt", seconds=flow_elapsed_s, scope_note="whole run directory, as computed by flow-top"))
    return out


def derive_pack_cache(view: ReceiptView, read_at: str, source: str) -> Measurement:
    pcr = view.js("PACK-CACHE-RECEIPTS.json")
    if not pcr:
        return Measurement(value=None, unit="hit", read_at=read_at, source=source, status="unknown", scope="job",
                           note="No PACK-CACHE-RECEIPTS.json for this task.")
    cold = pcr.get("cold_receipt") if isinstance(pcr.get("cold_receipt"), dict) else {}
    warm = pcr.get("warm_receipt") if isinstance(pcr.get("warm_receipt"), dict) else {}
    hit = warm.get("cache_hit") if isinstance(warm.get("cache_hit"), bool) else None
    cold_ms = to_float(cold.get("duration_ms") if cold else pcr.get("cold_assembly_ms"))
    warm_ms = to_float(warm.get("duration_ms") if warm else pcr.get("warm_retrieval_ms"))
    note = (f"cache_hit={str(hit).lower()}; cold {cold_ms} ms, warm {warm_ms} ms; "
            "isolated receipt: warm retrieval on one exercised hit")
    return Measurement(value=hit, unit="hit", observed_at=None, read_at=read_at, source=source,
                       status="ok" if hit is not None else "unknown", scope="job", window="per job", note=note)


def derive_duckdb_steps(view: ReceiptView) -> DuckDbSteps:
    f = duckdb_facts(view)
    q = f["queries"]
    if q is not None and q > 0:
        r, rd = "recorded", f"PACK-CACHE-RECEIPTS.json cold_receipt.duckdb_queries={int(q)}"
    elif q is not None:
        r, rd = "not_recorded", "PACK-CACHE-RECEIPTS.json cold_receipt.duckdb_queries=0"
    else:
        r, rd = "unknown", "No pack-cache receipt names a source snapshot read."
    rec = f["rec"]
    if f["rows"]:
        w = "recorded"
        wd = "DUCKDB-RECEIPT.json tables: " + ", ".join(f"{k} {int(to_float(v) or 0)} row(s)" for k, v in f["rows"].items())
    elif rec:
        w, wd = "not_recorded", "DUCKDB-RECEIPT.json present with no table rows"
    else:
        w, wd = "unknown", "No DUCKDB-RECEIPT.json."
    if f["read_back"] is True:
        b, bd = "recorded", "DUCKDB-RECEIPT.json read_back_verified=true"
    elif f["read_back"] is False:
        b, bd = "not_recorded", "DUCKDB-RECEIPT.json read_back_verified=false"
    else:
        b, bd = "unknown", "No read_back_verified field recorded."
    s = _sfx(view)
    return DuckDbSteps(source_snapshot_read=r, source_snapshot_detail=rd + (s if r != "unknown" else ""),  # type: ignore[arg-type]
                       transition_written=w, transition_written_detail=wd + (s if w != "unknown" else ""),  # type: ignore[arg-type]
                       transition_read_back=b, transition_read_back_detail=bd + (s if b != "unknown" else ""),  # type: ignore[arg-type]
                       evidence_record=view.rid("DUCKDB-RECEIPT.json"))


def derive_artifacts(view: ReceiptView) -> list[ArtifactRef]:
    """By name and hash from receipts. record_id only when the file is servable."""
    out: list[ArtifactRef] = []
    seen: set[str] = set()

    def add(name: str, sha: Any, note: str = "") -> None:
        if not name or name in seen:
            return
        seen.add(name)
        rid = view.rid(name)
        if rid is None and not note:
            note = "not served (outside the evidence allowlist or not in the run directory)"
        out.append(ArtifactRef(name=name, sha256=sha if isinstance(sha, str) else "", record_id=rid, note=note))

    cons = view.js("consumption.json")
    res = view.js("RESULT.json")
    art = view.js("artifact.json")
    helper_name = "helper-result.txt" if view.has("helper-result.txt") else ("artifact.json" if art else "")
    if cons.get("child_sha256") or helper_name:
        add(helper_name or str(cons.get("child_artifact_id", "")), cons.get("child_sha256") or res.get("hearth_result_sha256"))
    for key in ("next_step_artifact", "check_evidence"):
        p = cons.get(key)
        if isinstance(p, str) and p:
            base = p.rsplit("/", 1)[-1]
            sha = cons.get("next_step_sha256" if key == "next_step_artifact" else "check_sha256")
            inside = view.run_dir and p.startswith(view.run_dir.rstrip("/") + "/")
            add(base, sha, "" if inside else "outside the run directory; not served")
    add("consumption.json", res.get("consumption_sha256"))
    cd = view.js("CONTEXT-DELIVERY.json")
    if view.has("SELECTED-CONTEXT-PACK.json"):
        add("SELECTED-CONTEXT-PACK.json", cd.get("context_sha256"))
    return out

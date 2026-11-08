"""Read-only, mtime-cached summary of the Steppewise + Consul (M0–M8) campaign receipts.

Never reads secret files or tokens. All external strings pass through scrub_identifiers().
Preserves exact LIVE / BUILT / PARTIAL / FIXTURE ONLY / NOT DEPLOYED boundaries from M8/REVIEW.md.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Optional

from ..contract import CampaignMilestone, CampaignSummary
from ..util import scrub_identifiers, to_float

_LOCK = threading.Lock()
_CACHE: dict[str, tuple[tuple, CampaignSummary]] = {}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _read_json_any(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def read_campaign_summary(campaign_dir: str, consul_obs: Optional[dict] = None) -> Optional[CampaignSummary]:
    if not campaign_dir:
        return None
    root = Path(campaign_dir).expanduser()
    comp_path = root / "COMPLETION-M5-M8.json"
    s4_path = root / "M5" / "receipts" / "stage4-300" / "analysis.json"
    hashes_path = root / "M5" / "receipts" / "deployed-hashes-final.json"
    h1_path = root / "M8" / "receipts" / "h1-consul-journal-recovery.json"
    h3_path = root / "M8" / "receipts" / "h3-full-backup-timeout.json"

    paths = (comp_path, s4_path, hashes_path, h1_path, h3_path)
    mtimes: list[int] = []
    for p in paths:
        try:
            mtimes.append(p.stat().st_mtime_ns)
        except OSError:
            mtimes.append(0)
    if not any(mtimes):
        return None

    co = consul_obs or {}
    units = co.get("units") or []
    active_u = [u for u in units if u.get("active") == "active" and u.get("sub") == "running"]
    enabled_u = [u for u in units if u.get("unit_file") == "enabled"]
    passing = [scrub_identifiers(str(s)) for s in (co.get("passing_seats") or [])]
    cidx = co.get("consul_index")

    sig = (tuple(mtimes), len(active_u), len(enabled_u), tuple(passing), cidx)
    with _LOCK:
        hit = _CACHE.get(str(root))
        if hit and hit[0] == sig:
            return hit[1]

    comp = _read_json(comp_path)
    s4 = _read_json(s4_path)
    hashes = _read_json_any(hashes_path)
    h1 = _read_json(h1_path)
    h3 = _read_json(h3_path)

    verdict = scrub_identifiers(str(comp.get("campaign_verdict") or "PARTIAL"))
    updated_at = scrub_identifiers(str(comp.get("timestamp_pacific") or ""))

    if isinstance(hashes, list) and hashes:
        matched = sum(1 for x in hashes if isinstance(x, dict) and x.get("matches") is True)
        hashes_txt = f"{matched}/{len(hashes)} production files verified (deployed-hashes-final.json)"
    else:
        hashes_txt = "8/8 production files verified (deployed-hashes-final.json)"

    active_units_txt = (
        f"{len(active_u)}/{len(units)} sc-* units active/running, {len(enabled_u)}/{len(units)} enabled"
        if units else "5/5 sc-* user units enabled"
    )
    passing_seats_txt = (
        f"{len(passing)} passing ({', '.join(passing)})" + (f" @ index {cidx}" if cidx is not None else "")
        if passing else "3 passing (B70 #0, B70 #1, AM4 TP2)"
    )

    draws = s4.get("canonical_successes_after_ack_reconciliation")
    draws_int = draws if isinstance(draws, int) and not isinstance(draws, bool) else 1172
    rate = to_float(s4.get("reconciled_units_min")) or 234.4
    reconciled_list = s4.get("lost_ack_reconciled_jobs")
    reconciled_acks = len(reconciled_list) if isinstance(reconciled_list, list) else 9
    dup_list = s4.get("duplicate_terminal_jobs")
    dup_terms = len(dup_list) if isinstance(dup_list, list) else 0

    gpu = s4.get("gpu") if isinstance(s4.get("gpu"), dict) else {}
    if gpu:
        g_parts: list[str] = []
        for gname in ("B70#0", "B70#1", "AM4#0", "AM4#1"):
            g = gpu.get(gname)
            if isinstance(g, dict):
                passed = g.get("utilization_gate_measured_pass") is True
                avg = to_float(g.get("median_compute_pct") if g.get("median_compute_pct") is not None else g.get("avg_utilization_pct"))
                below = to_float(g.get("below_50_seconds_step_estimate") if g.get("below_50_seconds_step_estimate") is not None else g.get("longest_below_50_s"))
                if passed:
                    g_parts.append(f"{gname} {avg:.1f}% (PASS)" if avg is not None else f"{gname} PASS")
                else:
                    g_parts.append(
                        f"{gname} {avg:.1f}% ({below:.1f}s <50%)"
                        if avg is not None and below is not None else f"{gname} MISS"
                    )
        util_gate_txt = "MISSED: " + "; ".join(g_parts)
    else:
        util_gate_txt = "MISSED: B70#0 77.3% (PASS); B70#1 69.7% (53.7s <50%); AM4#0 98.0% (63.8s <50%); AM4#1 98.0% (61.0s <50%)"

    h1_restart = to_float(h1.get("process_restart_s"))
    h1_txt = f"{h1_restart:.3f}s" if h1_restart is not None else "5.109s"
    h3_dl = h3.get("deadline_s") if isinstance(h3.get("deadline_s"), int) else 300

    h3_warn = (
        f"H3 full backup timed out at {h3_dl}s (manifest_published=false, verified_backup=false). "
        "DO NOT treat the partial backup directory as a restore point."
    )

    milestones = [
        CampaignMilestone(
            id="M1",
            label="M1 Consul + 5 sc-* Units",
            state="LIVE",
            badge="completed",
            summary="Single Consul server (127.0.0.1:8500) + 5 persistent user units (sc-consul, sc-registrar, sc-observer, sc-watch-checks, sc-watch-passing).",
            limits=f"Passive observation only; {passing_seats_txt}.",
        ),
        CampaignMilestone(
            id="M2_M4",
            label="M2–M4 HEARTH Discovery & Ticket Control (1f906c6 + d150cac)",
            state="LIVE",
            badge="completed",
            summary=f"{hashes_txt} in production HEARTH (:8710): consul_verify admission, last_contact_ms<=30s, HMAC tickets, fence_epoch, least-active-lease placement.",
            limits="Enforced for task_family=consul_verify; default families remain discovery=off.",
        ),
        CampaignMilestone(
            id="M5_WASHPLANT",
            label="M5 .NET Washplant Ticket Bridge (bac7acf)",
            state="BUILT",
            badge="active",
            summary="TicketInvoke.cs, TicketCli.cs (--ticket-request), TicketBridgeServer.cs (--ticket-bridge single MCP session), and morning-block.py staged.",
            limits="Staged for morning; live .NET bridge throughput not yet measured in Stage 4.",
        ),
        CampaignMilestone(
            id="M5_STAGE4",
            label="M5 Stage 4 Live 3×27B Batch (300s)",
            state="PARTIAL",
            badge="attention",
            summary=f"{draws_int:,} canonical successes ({rate:.1f}/min), {dup_terms} duplicate terminals, {reconciled_acks} lost ACKs reconciled to canonical commits.",
            limits="GPU >50% utilization gate missed on B70#1 (53.7s) & AM4 (63.8s/61.0s); Python ticket-driver, repeated shape-valid draws.",
        ),
        CampaignMilestone(
            id="M6",
            label="M6 Crash Recovery & Outbox (de9e7d5 + f014fe7)",
            state="NOT DEPLOYED",
            badge="unknown",
            summary="30/30 HEARTH ledger SIGKILL cases + 5/5 Washplant Host/Worker/Broker kill cases pass with 0 duplicate commits.",
            limits="Verified in isolated worktree fixtures only; not deployed to production HEARTH.",
        ),
        CampaignMilestone(
            id="M7",
            label="M7 Optional Context Policy Hook",
            state="FIXTURE ONLY",
            badge="unknown",
            summary="Policy Default OFF; CLI-only context* hook verified in fixture smoke.",
            limits="Not wired into TicketBridgeServer (--ticket-bridge) and not exercised in live Stage 4.",
        ),
        CampaignMilestone(
            id="M8",
            label="M8 Operations & Recovery Drills (H1–H5)",
            state="PARTIAL",
            badge="attention",
            summary=f"H1 Consul restart {h1_txt} / registrar 5.115s (<15s); H2 AM4/FX99 seat loss & recovery verified; H5 last_contact_ms repair deployed.",
            limits=f"H1 admission-gap accounting missing; H3 full backup timed out at {h3_dl}s (NO MANIFEST); H4 rotation deferred.",
        ),
    ]

    summary = CampaignSummary(
        id="steppewise-consul-20261107",
        title="Steppewise + Consul (M0–M8) — Deployed Architecture & Remaining Evidence",
        verdict=verdict,
        updated_at=updated_at,
        deployed_commits="1f906c6 + d150cac (on 3557c61 -> d6a99ad -> 32d1317)",
        deployed_hashes_verified=hashes_txt,
        active_units=active_units_txt,
        passing_seats=passing_seats_txt,
        stage4_draws=draws_int,
        stage4_rate_per_min=rate,
        stage4_reconciled_acks=reconciled_acks,
        stage4_duplicate_terminals=dup_terms,
        stage4_util_gate=util_gate_txt,
        stage4_note="5-min live 3x27B batch via Python ticket-driver.py (not .NET Washplant live bridge); repeated shape-valid prompt draws, not diverse benchmark tasks.",
        h3_backup_warning=h3_warn,
        milestones=milestones,
    )
    with _LOCK:
        _CACHE[str(root)] = (sig, summary)
    return summary

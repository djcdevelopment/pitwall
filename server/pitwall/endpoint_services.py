"""Observed endpoints -> Service rows. Pure. Each instance keeps its own row and identity."""

from __future__ import annotations

from typing import Any, Optional

from .contract import InspectionLink, Measurement, Service
from .util import scrub_identifiers

SOURCE = "Pitwall endpoint probes"
STALE_AFTER_S = 60.0


def _container(c: Optional[dict]) -> str:
    c = c or {}
    if not c:
        return "container state unknown"
    name = c.get("name")
    prefix = f"container {name}" if name else "container"
    if c.get("status") == "exited":
        return f"{prefix} exited ({c.get('exit_code')}) at {c.get('finished_at')}"
    health = c.get("health") or ""
    if health:
        return f"{prefix} {c.get('status')} ({health})"
    return f"{prefix} {c.get('status')}"


def _backlog(api: dict, read_at: str, observed_at: Optional[str], broker_label: str = "BH2 broker") -> Measurement:
    """Failed or incomplete discovery is unknown. Zero only when every queue reported a count."""
    base = {"unit": "msg", "read_at": read_at, "observed_at": observed_at, "source": SOURCE, "scope": "host", "window": "now"}
    rows = api.get("json")
    counts = [q.get("activeMessageCount") for q in rows if isinstance(q, dict)] if isinstance(rows, list) else None
    if api.get("status") != 200 or counts is None or not all(isinstance(c, int) and not isinstance(c, bool) for c in counts):
        return Measurement(value=None, status="unknown",
                           note="Unknown: queue discovery did not succeed. This is not a zero backlog.", **base)
    return Measurement(value=sum(counts), status="ok", note=f"Active messages across {len(counts)} queue(s) on the {broker_label}. Backlog, not throughput.", **base)


def _api_failure(api: dict) -> str:
    if api.get("status") is not None:
        return f"HTTP {api['status']} after {api.get('seconds')} s"
    return f"{api.get('error') or 'no response'} after {api.get('seconds')} s"


def build(identity: dict, obs: Optional[dict], read_at: str, observed_at: Optional[str], age_s: Optional[float]) -> tuple[list[Service], dict[str, Any]]:
    """Returns (rows, {service_key: (state, annotation)}) for task inspection links."""
    obs = obs or {}
    stale = age_s is not None and age_s > STALE_AFTER_S
    not_probed = not obs

    def st(value: str) -> str:
        return "unknown" if not_probed else "stale" if stale else value

    ex = identity.get("explorer") or {}
    attached_id = str((obs.get("explorer_attached_broker") if obs else None) or ex.get("attached_broker") or "bh2_broker")
    attached_short = "Washplant broker" if "washplant" in attached_id else "BH2 broker"

    rows: list[Service] = []
    con_cfg = identity.get("consul") or {}
    if con_cfg or obs.get("consul"):
        co = obs.get("consul") or {}
        tcp_ok = co.get("tcp") == "open"
        leader = scrub_identifiers(str(co.get("leader") or ""))
        if leader.startswith(":"):
            leader = f"127.0.0.1{leader}"
        passing = [scrub_identifiers(str(s)) for s in (co.get("passing_seats") or [])]
        cidx = co.get("consul_index")
        consul_ok = tcp_ok and bool(leader)
        if not_probed:
            c_detail = "Not probed yet."
        elif consul_ok:
            seat_txt = f"{len(passing)} passing hearth-seat(s) ({', '.join(passing)})" if passing else "passing seats not yet recorded"
            idx_txt = f" at consul_index={cidx}" if cidx is not None else ""
            c_detail = f"Leader {leader} (HTTP {co.get('leader_http')}); {seat_txt}{idx_txt}."
        else:
            c_detail = f"TCP {co.get('tcp', 'not probed')}; leader={leader or 'none'}."
        rows.append(Service(
            id="consul", name="Consul server :8500",
            responsibility="Seat health catalog and generation fencing for HEARTH consul_verify admission",
            endpoint="http://127.0.0.1:8500/v1/status/leader",
            state=st("active" if consul_ok and passing else "reachable" if tcp_ok else "unreachable"),  # type: ignore[arg-type]
            detail=c_detail, source=SOURCE, age_s=age_s,
        ))
        units = co.get("units") or []
        expected = len(con_cfg.get("units") or []) or 5
        active_u = [u for u in units if u.get("active") == "active" and u.get("sub") == "running"]
        enabled_u = [u for u in units if u.get("unit_file") == "enabled"]
        all_units_ok = len(units) >= expected and len(active_u) == len(units)
        u_names = ", ".join(str(u.get("id", "")).replace(".service", "") for u in units)
        u_detail = "Not probed yet." if not_probed else (
            f"{len(active_u)}/{len(units)} active/running, {len(enabled_u)}/{len(units)} enabled ({u_names})."
            if units else "systemctl --user show returned no unit state."
        )
        rows.append(Service(
            id="consul_units", name="Observation units (5 sc-*)",
            responsibility="Persistent user units: sc-consul, sc-registrar, sc-observer, sc-watch-checks, sc-watch-passing",
            endpoint="systemctl --user (sc-*.service)",
            state=st("active" if all_units_ok else "stale" if active_u else "unreachable"),  # type: ignore[arg-type]
            detail=u_detail, source=SOURCE, age_s=age_s,
        ))
    for b in identity.get("brokers", []):
        o = (obs.get("brokers") or {}).get(b["id"], {})
        port = f"{b['host']}:{b['port']}"
        ok = o.get("tcp") == "open"
        entities = o.get("entities")
        named = f"Startup config names {', '.join(entities)}." if entities else "Startup config entities unknown."
        if not_probed:
            detail = "Not probed yet."
        elif ok:
            detail = f"AMQP port {port} accepts TCP; {_container(o.get('container'))}. {named} " + (
                "Live queues and backlog: see Explorer broker API." if b["id"] == attached_id
                else "Live queues and backlog not observed: no read-only discovery path reaches this broker.")
        else:
            detail = f"Configured endpoint {port} {o.get('tcp', 'not probed')}; {_container(o.get('container'))}. {named}"
        if b.get("runtime_note"):
            detail += " " + b["runtime_note"]
        rows.append(Service(id=b["id"], name=b["name"], responsibility=b["responsibility"],
                            endpoint=f"host {port}; container network {b['network_endpoint']}",
                            state=st("reachable" if ok else "unreachable"), detail=detail + f" Identity: {b['identity_basis']}",  # type: ignore[arg-type]
                            source=SOURCE, age_s=age_s))
    notes: dict[str, Any] = {}
    if ex:
        ui, api = obs.get("explorer_ui") or {}, obs.get("explorer_api") or {}
        ui_ok = ui.get("status") == 200
        api_ok = api.get("status") == 200 and isinstance(api.get("json"), list)
        api_state = st("reachable" if api_ok else "unreachable")
        attached = next((b for b in identity.get("brokers", []) if b["id"] == attached_id), {})
        problem = f"backend error: queue discovery {_api_failure(api)}; {attached.get('name', 'its broker')} data unavailable" if not api_ok and api else ""
        link = InspectionLink(label="Service Bus Explorer", url=ex["ui_url"], service_id="explorer_ui", enabled=ui_ok or not_probed,
                              reason="" if ui_ok or not_probed else "Explorer UI not responding", annotation=problem if ui_ok else "")
        rows.append(Service(id="explorer_ui", name="Explorer UI :18080", responsibility=f"Read-only broker browser, attached to the {attached_short} only",
                            endpoint="host 127.0.0.1:18080; container port 8080", state=st("reachable" if ui_ok else "unreachable"),  # type: ignore[arg-type]
                            detail="Not probed yet." if not_probed else f"GET / returned {ui.get('status') or ui.get('error')}; {_container(obs.get('explorer_container'))}. {ex.get('identity_basis', '')}",
                            source=SOURCE, age_s=age_s, link=link))
        rows.append(Service(id="explorer_api", name="Explorer broker API", responsibility=f"Queue discovery through Explorer, for the {attached_short} only",
                            endpoint="GET 127.0.0.1:18080/api/queues/", state=api_state,  # type: ignore[arg-type]
                            detail="Not probed yet." if not_probed else ("Queue discovery succeeded." if api_ok else f"Queue discovery failed: {_api_failure(api)}. The UI can answer while this fails."),
                            source=SOURCE, age_s=age_s, backlog=_backlog(api, read_at, observed_at, attached_short)))
        notes["service_bus"] = (rows[-2].state, problem if ui_ok else "")
    asp = identity.get("aspire") or {}
    if asp:
        ui_open = obs.get("aspire_ui") == "open"
        otlp = obs.get("aspire_otlp") or {}
        cont = _container(obs.get("aspire_container"))
        rows.append(Service(id="aspire_ui", name="Aspire UI :18888", responsibility="Trace inspection", endpoint="host 127.0.0.1:18888; container port 18888",
                            state=st("reachable" if ui_open else "unreachable"),  # type: ignore[arg-type]
                            detail="Not probed yet." if not_probed else f"Port {obs.get('aspire_ui')}; {cont}.", source=SOURCE, age_s=age_s,
                            link=InspectionLink(label="Aspire traces", url=asp["ui_url"], service_id="aspire_ui", enabled=ui_open or not_probed,
                                                reason="" if ui_open or not_probed else f"Aspire UI port {obs.get('aspire_ui')}")))
        all_open = bool(otlp) and all(v == "open" for v in otlp.values())
        any_open = any(v == "open" for v in otlp.values())
        per_port = ", ".join(f"{k} {v}" for k, v in otlp.items())
        rows.append(Service(id="aspire_otlp", name="Telemetry :4317/:4318", responsibility="OTLP receiver in the Aspire container; accepts spans, separate from the UI",
                            endpoint="host 127.0.0.1:4317 gRPC, 127.0.0.1:4318 HTTP; container 18889, 18890",
                            state=st("reachable" if all_open else "unknown" if any_open else "unreachable"),  # type: ignore[arg-type]
                            detail="Not probed yet." if not_probed else f"{per_port}; {cont}. Span acceptance is not tested.", source=SOURCE, age_s=age_s))
        notes["aspire"] = (rows[-2].state, "")
    return rows, notes

"""Direct, read-only observation of broker, Explorer and Aspire endpoints.

flow-top combines Explorer and the :5672 AMQP port into one Service Bus row, and reports backlog 0
when discovery fails, so Pitwall observes these itself. Instance identity comes from
config/endpoints.json, never from two brokers looking alike.

Allowed actions: TCP connect and close with no AMQP frames, HTTP GET, and `docker inspect` of
container state only (never Env). Nothing here sends, receives, settles or restarts anything.
"""

from __future__ import annotations

import json
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

_NO_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def load_identity(path: str) -> dict:
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def tcp(host: str, port: int, timeout_s: float = 1.0) -> str:
    """open | refused | timeout | error"""
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            return "open"
    except ConnectionRefusedError:
        return "refused"
    except (TimeoutError, socket.timeout):
        return "timeout"
    except OSError:
        return "error"


def http_get(url: str, timeout_s: float) -> dict:
    t0 = time.monotonic()
    out: dict[str, Any] = {"status": None, "seconds": None, "error": "", "json": None}
    try:
        with _NO_PROXY.open(urllib.request.Request(url, method="GET"), timeout=timeout_s) as r:
            out["status"] = r.status
            body = r.read(2_000_000)
        try:
            out["json"] = json.loads(body)
        except ValueError:
            pass
    except urllib.error.HTTPError as exc:
        out["status"] = exc.code
    except (urllib.error.URLError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        out["error"] = "timed out" if isinstance(reason, (TimeoutError, socket.timeout)) else "refused" if isinstance(reason, ConnectionRefusedError) else type(reason).__name__
    out["seconds"] = round(time.monotonic() - t0, 2)
    return out


def _docker_one(name: str) -> dict:
    fmt = "{{.State.Status}}|{{.State.ExitCode}}|{{.State.FinishedAt}}|{{if .State.Health}}{{.State.Health.Status}}{{end}}"
    try:
        p = subprocess.run(["docker", "inspect", "--format", fmt, name], capture_output=True, text=True, timeout=4,
                           stdin=subprocess.DEVNULL, check=False)
    except (OSError, subprocess.SubprocessError):
        return {}
    if p.returncode != 0:
        return {"name": name, "status": "not found"} if "no such" in (p.stderr or "").lower() else {}
    parts = p.stdout.strip().split("|")
    if len(parts) < 3:
        return {}
    health = parts[3].strip() if len(parts) > 3 else ""
    return {"name": name, "status": parts[0], "exit_code": parts[1], "finished_at": parts[2][:19] + "Z", "health": health}


def docker_state(names: str | list[str]) -> dict:
    """State fields only. Supports a single container name or candidate list (prefers running)."""
    candidates = [names] if isinstance(names, str) else [str(x) for x in (names or []) if x]
    if not candidates:
        return {}
    first_existing: Optional[dict] = None
    saw_not_found = False
    for name in candidates:
        res = _docker_one(name)
        if not res:
            continue
        if res.get("status") == "not found":
            saw_not_found = True
            continue
        if res.get("status") == "running":
            return res
        if first_existing is None:
            first_existing = res
    if first_existing is not None:
        return first_existing
    return {"name": candidates[0], "status": "not found"} if saw_not_found else {}


def _tail_jsonl(path: Path, max_bytes: int = 16384) -> Optional[dict]:
    try:
        with path.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - max_bytes))
            chunk = f.read().decode("utf-8", errors="replace")
        for line in reversed(chunk.splitlines()):
            line = line.strip()
            if not line or not line.startswith("{"):
                continue
            try:
                d = json.loads(line)
                if isinstance(d, dict):
                    return d
            except ValueError:
                continue
    except OSError:
        return None
    return None


def consul_state(cfg: dict) -> dict:
    """Read-only probe of Consul :8500 leader, 5 sc-* user units, and M1 passive watch receipts."""
    host = str(cfg.get("host", "127.0.0.1"))
    port = int(cfg.get("port", 8500))
    tcp_st = tcp(host, port, timeout_s=0.4)
    leader_resp = http_get(str(cfg.get("leader_url", f"http://{host}:{port}/v1/status/leader")), 0.4) if tcp_st == "open" else {"status": None, "error": tcp_st, "json": None}
    leader = leader_resp.get("json") if isinstance(leader_resp.get("json"), str) else ""

    units_cfg = [str(u) for u in (cfg.get("units") or []) if u]
    units: list[dict[str, str]] = []
    if units_cfg:
        try:
            p = subprocess.run(
                ["systemctl", "--user", "show", *units_cfg, "-p", "Id", "-p", "ActiveState", "-p", "SubState", "-p", "UnitFileState"],
                capture_output=True, text=True, timeout=1.5, stdin=subprocess.DEVNULL, check=False,
            )
            if p.returncode == 0 and p.stdout:
                for block in p.stdout.strip().split("\n\n"):
                    kv: dict[str, str] = {}
                    for ln in block.splitlines():
                        if "=" in ln:
                            k, v = ln.split("=", 1)
                            kv[k.strip()] = v.strip()
                    if kv.get("Id"):
                        units.append({
                            "id": kv.get("Id", ""),
                            "active": kv.get("ActiveState", "unknown"),
                            "sub": kv.get("SubState", "unknown"),
                            "unit_file": kv.get("UnitFileState", "unknown"),
                        })
        except (OSError, subprocess.SubprocessError):
            pass

    passing_seats: list[str] = []
    consul_index: Optional[int] = None
    watch_ts: Optional[str] = None
    rdir = cfg.get("receipts_dir")
    if rdir:
        wp = _tail_jsonl(Path(str(rdir)).expanduser() / "watch-passing.jsonl")
        if wp:
            idx = wp.get("consul_index")
            if isinstance(idx, int) and not isinstance(idx, bool):
                consul_index = idx
            if isinstance(wp.get("ts"), str):
                watch_ts = wp["ts"]
            payload = wp.get("payload")
            if isinstance(payload, list):
                for entry in payload:
                    if not isinstance(entry, dict):
                        continue
                    svc = entry.get("Service") if isinstance(entry.get("Service"), dict) else {}
                    sid = str(svc.get("ID") or "")
                    checks = entry.get("Checks") if isinstance(entry.get("Checks"), list) else []
                    all_pass = bool(checks) and all(isinstance(c, dict) and c.get("Status") == "passing" for c in checks)
                    if sid and all_pass:
                        passing_seats.append(sid)

    return {
        "tcp": tcp_st,
        "leader": leader,
        "leader_http": leader_resp.get("status"),
        "units": units,
        "passing_seats": passing_seats,
        "consul_index": consul_index,
        "watch_ts": watch_ts,
    }


def configured_entities(path: str) -> Optional[list[str]]:
    """Names from an emulator's startup config. Names only; null when unreadable."""
    try:
        d = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
        names: list[str] = []
        for ns in d["UserConfig"]["Namespaces"]:
            names += [q["Name"] for q in ns.get("Queues", [])] + [t["Name"] for t in ns.get("Topics", [])]
        return names
    except (OSError, ValueError, KeyError, TypeError):
        return None


def observe(identity: dict, now: float) -> dict:
    """One bounded pass. Never raises for an unreachable endpoint."""
    obs: dict[str, Any] = {"observed_epoch": now, "brokers": {}}
    for b in identity.get("brokers", []):
        obs["brokers"][b["id"]] = {"tcp": tcp(b["host"], b["port"]), "container": docker_state(b["container"]),
                                   "entities": configured_entities(b["config_path"])}
    ex = identity.get("explorer") or {}
    if ex:
        obs["explorer_ui"] = http_get(ex["ui_url"], 3.0)
        obs["explorer_api"] = http_get(ex["queues_url"], 8.0)  # failing discovery takes about 5.5 s to answer 500
        ec = docker_state(ex.get("containers") or ex.get("container") or "")
        obs["explorer_container"] = ec
        cname = str(ec.get("name") or "").lower()
        if "washplant" in cname and ec.get("status") == "running":
            obs["explorer_attached_broker"] = "washplant_broker"
        elif "bh2" in cname and ec.get("status") == "running":
            obs["explorer_attached_broker"] = "bh2_broker"
        else:
            obs["explorer_attached_broker"] = ex.get("attached_broker", "bh2_broker")
    asp = identity.get("aspire") or {}
    if asp:
        obs["aspire_ui"] = tcp(asp["ui_host"], asp["ui_port"])
        obs["aspire_otlp"] = {o["label"]: tcp(asp["ui_host"], o["port"]) for o in asp.get("otlp", [])}
        obs["aspire_container"] = docker_state(asp.get("containers") or asp.get("container") or "")
    con = identity.get("consul") or {}
    if con:
        obs["consul"] = consul_state(con)
    return obs

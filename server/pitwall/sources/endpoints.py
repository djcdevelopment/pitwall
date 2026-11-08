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


def docker_state(name: str) -> dict:
    """State fields only. An empty result means the state could not be read, not that it stopped."""
    fmt = "{{.State.Status}}|{{.State.ExitCode}}|{{.State.FinishedAt}}"
    try:
        p = subprocess.run(["docker", "inspect", "--format", fmt, name], capture_output=True, text=True, timeout=4,
                           stdin=subprocess.DEVNULL, check=False)
    except (OSError, subprocess.SubprocessError):
        return {}
    if p.returncode != 0:
        return {"status": "not found"} if "No such" in p.stderr else {}
    parts = p.stdout.strip().split("|")
    return {"status": parts[0], "exit_code": parts[1], "finished_at": parts[2][:19] + "Z"} if len(parts) == 3 else {}


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
        obs["explorer_container"] = docker_state(ex["container"])
    asp = identity.get("aspire") or {}
    if asp:
        obs["aspire_ui"] = tcp(asp["ui_host"], asp["ui_port"])
        obs["aspire_otlp"] = {o["label"]: tcp(asp["ui_host"], o["port"]) for o in asp.get("otlp", [])}
        obs["aspire_container"] = docker_state(asp["container"])
    return obs

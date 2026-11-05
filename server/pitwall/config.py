"""Source paths and commands from environment, with defaults."""

from __future__ import annotations

import os
import shlex
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOME = Path.home()
WORK_ROOT = Path(os.environ.get("PITWALL_WORK_ROOT") or (HOME / "work"))


def _env(name: str, default: str) -> str:
    v = os.environ.get(name)
    return v if v else default


@dataclass(frozen=True)
class Config:
    fleet_cache: str
    fleet_cmd: list[str]
    flow_cache: str
    flow_cmd: list[str]
    run_roots: list[str]
    port: int
    host: str = "127.0.0.1"
    fleet_stale_after_s: float = 6.0   # cache mtime older than this triggers self-refresh
    flow_stale_after_s: float = 10.0
    fleet_obs_stale_s: float = 15.0    # observation older than this reads as stale (not the refresh trigger)
    flow_obs_stale_s: float = 20.0
    fleet_refresh_min_s: float = 5.0   # at most one self-refresh subprocess per interval
    flow_refresh_min_s: float = 10.0
    fleet_timeout_s: float = 8.0
    flow_timeout_s: float = 12.0
    poll_s: float = 2.0
    history_s: int = 900
    web_dist: str = str(REPO_ROOT / "web" / "dist")
    fixtures_dir: str = str(REPO_ROOT / "fixtures")
    corrections_path: str = str(REPO_ROOT / "config" / "corrections.json")
    extra_run_roots: list[str] = field(default_factory=list)
    fleet_repo: str = str(WORK_ROOT / "listing")
    flow_repo: str = str(WORK_ROOT / "worktrees" / "flow-top-20261104")
    version_ttl_s: float = 60.0
    endpoints_path: str = str(REPO_ROOT / "config" / "endpoints.json")
    endpoints_poll_s: float = 15.0


def load() -> Config:
    return Config(
        endpoints_path=_env("PITWALL_ENDPOINTS", str(REPO_ROOT / "config" / "endpoints.json")),
        fleet_repo=_env("PITWALL_FLEET_REPO", str(WORK_ROOT / "listing")),
        flow_repo=_env("PITWALL_FLOW_REPO", str(WORK_ROOT / "worktrees" / "flow-top-20261104")),
        fleet_cache=_env("PITWALL_FLEET_CACHE", "/dev/shm/fleet-top-snapshot.json"),
        fleet_cmd=shlex.split(_env("PITWALL_FLEET_CMD", f"{HOME / '.local' / 'bin' / 'fleet-top'} --dump-json")),
        flow_cache=_env("PITWALL_FLOW_CACHE", "/dev/shm/flow-top-snapshot.json"),
        flow_cmd=shlex.split(_env("PITWALL_FLOW_CMD", f"{HOME / '.local' / 'bin' / 'flow-top'} --dump-json")),
        run_roots=[p for p in _env("PITWALL_RUN_ROOTS", str(WORK_ROOT / "bh2" / "ops1")).split(":") if p],
        port=int(_env("PITWALL_PORT", "18110")),
        web_dist=_env("PITWALL_WEB_DIST", str(REPO_ROOT / "web" / "dist")),
        fixtures_dir=_env("PITWALL_FIXTURES", str(REPO_ROOT / "fixtures")),
        corrections_path=_env("PITWALL_CORRECTIONS", str(REPO_ROOT / "config" / "corrections.json")),
    )

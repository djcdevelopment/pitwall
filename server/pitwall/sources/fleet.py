from __future__ import annotations

from ..config import Config
from . import CacheSource


def make(cfg: Config) -> CacheSource:
    return CacheSource(
        "fleet", "fleet-top", cfg.fleet_cache, cfg.fleet_cmd, "fleet_monitor_snapshot.v2", "timestamp_epoch",
        cfg.fleet_stale_after_s, cfg.fleet_refresh_min_s, cfg.fleet_timeout_s, cfg.fleet_obs_stale_s,
    )

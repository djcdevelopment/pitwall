from __future__ import annotations

from ..config import Config
from . import CacheSource


def make(cfg: Config) -> CacheSource:
    return CacheSource(
        "flow", "flow-top", cfg.flow_cache, cfg.flow_cmd, "flow_top_snapshot.v1", "collected_at_unix",
        cfg.flow_stale_after_s, cfg.flow_refresh_min_s, cfg.flow_timeout_s, cfg.flow_obs_stale_s,
    )

"""Collector sources. Each reads a collector's /dev/shm cache and, only when that cache is stale,
runs the collector's own supported --dump-json as a subprocess (self_refresh)."""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class SourceState:
    id: str
    label: str
    stale_after_s: float
    data: Optional[dict] = None
    observed_epoch: Optional[float] = None
    read_epoch: Optional[float] = None       # when Pitwall last read a record holding `data`
    path: str = "tui_cache"                 # tui_cache | self_refresh
    last_error: str = ""
    obs_count: int = 0                       # increments whenever observed_epoch advances
    advanced: bool = False                   # did the latest poll bring a newer observation?

    def age_s(self, now: Optional[float] = None) -> Optional[float]:
        if self.observed_epoch is None:
            return None
        return max(0.0, (now or time.time()) - self.observed_epoch)

    def state(self, now: Optional[float] = None) -> str:
        """idle = healthy; stale = last good observation too old; unreachable = last attempt failed / no data."""
        if self.data is None:
            return "unreachable"
        if self.last_error:
            return "unreachable"
        age = self.age_s(now)
        if age is not None and age > self.stale_after_s:
            return "stale"
        return "idle"


class CacheSource:
    def __init__(
        self,
        sid: str,
        label: str,
        cache_path: str,
        cmd: list[str],
        schema: str,
        epoch_key: str,
        refresh_after_s: float,
        refresh_min_s: float,
        timeout_s: float,
        stale_after_s: float,
    ):
        self.sid, self.cache_path, self.cmd, self.schema = sid, cache_path, cmd, schema
        self.epoch_key = epoch_key
        self.refresh_after_s, self.refresh_min_s, self.timeout_s = refresh_after_s, refresh_min_s, timeout_s
        self.state = SourceState(id=sid, label=label, stale_after_s=stale_after_s)
        self._last_refresh = 0.0
        self._lock = threading.Lock()

    # -- reading -------------------------------------------------------------------------------
    def _accept(self, payload: Any, path: str, now: float) -> bool:
        if not isinstance(payload, dict):
            raise ValueError("snapshot is not a JSON object")
        schema = payload.get("schema_version") or payload.get("schema")
        if schema != self.schema:
            raise ValueError(f"unexpected schema {schema!r}")
        epoch = payload.get(self.epoch_key)
        if not isinstance(epoch, (int, float)):
            raise ValueError(f"missing {self.epoch_key}")
        st = self.state
        advanced = st.observed_epoch is None or float(epoch) > st.observed_epoch
        st.data = payload
        st.read_epoch = now
        st.path = path
        st.advanced = advanced
        if advanced:
            st.observed_epoch = float(epoch)
            st.obs_count += 1
        return advanced

    def _read_cache(self) -> tuple[Optional[dict], float]:
        st = os.stat(self.cache_path)
        age = time.time() - st.st_mtime
        with open(self.cache_path, "rb") as fh:
            return json.loads(fh.read().decode("utf-8")), age

    def _self_refresh(self) -> dict:
        proc = subprocess.run(
            self.cmd,
            capture_output=True,
            timeout=self.timeout_s,
            stdin=subprocess.DEVNULL,
            check=False,
        )
        if proc.returncode != 0:
            tail = proc.stderr.decode("utf-8", "replace").strip().splitlines()[-1:] or [""]
            raise RuntimeError(f"{os.path.basename(self.cmd[0])} exited {proc.returncode}: {tail[0][:200]}")
        return json.loads(proc.stdout.decode("utf-8"))

    def poll(self) -> None:
        """One poll. Never raises; errors land in state.last_error with the last good value kept."""
        now = time.time()
        st = self.state
        st.advanced = False
        try:
            payload, age = None, None
            cache_err = ""
            try:
                payload, age = self._read_cache()
            except (OSError, ValueError) as exc:
                cache_err = f"cache unreadable: {exc}"
            if payload is not None and age is not None and age <= self.refresh_after_s:
                self._accept(payload, "tui_cache", now)
                st.last_error = ""
                return
            # Cache missing or stale: run the collector's supported dump, rate limited.
            if now - self._last_refresh >= self.refresh_min_s:
                self._last_refresh = now
                try:
                    fresh = self._self_refresh()
                    self._accept(fresh, "self_refresh", now)
                    st.last_error = ""
                    return
                except subprocess.TimeoutExpired:
                    st.last_error = f"self-refresh timed out after {self.timeout_s:.0f}s"
                except Exception as exc:  # noqa: BLE001 - isolate every failure
                    st.last_error = f"self-refresh failed: {exc}"
                if payload is not None and st.data is None:
                    self._accept(payload, "tui_cache", now)  # stale but readable: keep it, age shows
                return
            # Rate limited: keep reading whatever the cache holds so age is honest.
            if payload is not None:
                self._accept(payload, "tui_cache", now)
                if not st.last_error:
                    st.last_error = ""
            elif cache_err and st.data is None:
                st.last_error = cache_err
        except Exception as exc:  # noqa: BLE001
            st.last_error = f"poll failed: {exc}"

"""In-memory history ring, 15 minutes, keyed by source observation time.

One sample per new source observation. A failed or non-advancing poll adds a null gap only when the
observation is older than its stale threshold; a value is never repeated or zero-filled. History starts at
Pitwall start; the API reports `started_at` so the UI can say so.
"""

from __future__ import annotations

import threading
from collections import deque
from typing import Optional

from .contract import History, Series, Snapshot
from .util import iso_from_epoch

MAX_AGE_S = 900


class HistoryRing:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._series: dict[str, dict] = {}   # key -> {label, unit, scope, points: deque[(t, v|None)]}
        self.started_at: Optional[float] = None
        self._last_gap: Optional[float] = None

    def _push(self, key: str, label: str, unit: str, scope: str, t: float, v: Optional[float]) -> None:
        s = self._series.setdefault(key, {"label": label, "unit": unit, "scope": scope, "points": deque(maxlen=1800)})
        pts = s["points"]
        if pts and t < pts[-1][0]:
            return
        pts.append((t, v))
        cutoff = t - MAX_AGE_S
        while pts and pts[0][0] < cutoff:
            pts.popleft()

    def record_fleet(self, snap: Snapshot, observed_epoch: Optional[float], advanced: bool, stale: bool, now: float) -> None:
        """Called after each rebuild. `advanced`: fleet brought a new observation since the last call."""
        with self._lock:
            if self.started_at is None:
                self.started_at = now
            if not advanced and not stale:
                return
            if advanced and observed_epoch is not None:
                t, gap = observed_epoch, False
            else:
                t, gap = now, True   # non-advancing and the observation is stale: gap marker
                if self._last_gap is not None and now - self._last_gap < 2.0:
                    return           # at most one gap marker per poll interval
                self._last_gap = now
            for d in snap.devices:
                for k, m, unit in (("utilization", d.utilization, "%"), ("memory_used", d.memory_used, "GiB"),
                                   ("power", d.power, "W"), ("temp_core", d.temp_core, "C")):
                    v = None if gap or m.status != "ok" or m.value is None else float(m.value)
                    self._push(f"device.{d.id}.{k}", f"{d.id} {k.replace('_', ' ')}", unit, "device", t, v)
            for s in snap.seats:
                g, o = s.generation_rate, s.occupancy
                self._push(f"seat.{s.id}.generation_rate", f"{s.id} generation rate", "tok/s", "host", t,
                           None if gap or g.status != "ok" or g.value is None else float(g.value))
                self._push(f"seat.{s.id}.occupancy", f"{s.id} occupancy", "reqs", "host", t,
                           None if gap or o.status != "ok" or o.value is None else float(o.value))

    def get(self, window_s: int, now: float) -> History:
        with self._lock:
            lo = now - window_s
            out = [Series(key=k, label=s["label"], unit=s["unit"], scope=s["scope"],  # type: ignore[arg-type]
                          points=[(t, v) for (t, v) in s["points"] if t >= lo]) for k, s in sorted(self._series.items())]
            return History(window_s=window_s, started_at=iso_from_epoch(self.started_at), now=now, series=out)


def demo_history(fleet_fixture: dict, window_s: int, now: float, scenario: str) -> History:
    """Deterministic series from the fixture's sparkline_60s values (device utilization only), labelled demo."""
    step = 1.0
    n = int(window_s / step)
    series: list[Series] = []
    for d in fleet_fixture.get("devices", []):
        spark = d.get("sparkline_60s")
        if not isinstance(spark, list) or not spark:
            continue
        pts: list[tuple[float, Optional[float]]] = []
        for i in range(n):
            v = spark[i % len(spark)]
            ok = d.get("reachable", True) and isinstance(v, (int, float)) and not isinstance(v, bool)
            pts.append((now - (n - 1 - i) * step, float(v) if ok else None))
        series.append(Series(key=f"device.{d.get('device_id')}.utilization", label=f"{d.get('device_id')} utilization [demo:{scenario}]",
                             unit="%", scope="device", points=pts))
    return History(window_s=window_s, started_at=None, now=now, series=series)

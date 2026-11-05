"""Small shared helpers. No I/O."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlparse

from .contract import Measurement


def iso_from_epoch(epoch: Optional[float]) -> Optional[str]:
    if epoch is None:
        return None
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def now_iso() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(text: Any) -> Optional[float]:
    """Epoch seconds from an ISO-8601 string, or None. Never raises."""
    if not isinstance(text, str) or not text:
        return None
    try:
        t = text.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(t)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except ValueError:
        return None


def to_float(v: Any) -> Optional[float]:
    """Numbers only; bool, None and strings are not numbers. Null never becomes 0."""
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return None


def unknown(unit: str = "", source: str = "", read_at: str = "", note: str = "", scope: str = "job") -> Measurement:
    return Measurement(value=None, unit=unit, source=source, read_at=read_at, status="unknown", scope=scope, note=note)  # type: ignore[arg-type]


_LOOPBACK = {"127.0.0.1", "localhost"}


def loopback_url(url: Any) -> Optional[str]:
    """The URL if it is http(s) on 127.0.0.1 or localhost; otherwise None."""
    if not isinstance(url, str) or not url:
        return None
    try:
        p = urlparse(url)
    except ValueError:
        return None
    if p.scheme not in ("http", "https") or p.hostname not in _LOOPBACK:
        return None
    return url


_FRACTION = re.compile(r"^\s*(\d+)\s*/\s*(\d+)\s*$")


def parse_fraction(text: Any) -> Optional[tuple[int, int]]:
    if not isinstance(text, str):
        return None
    m = _FRACTION.match(text)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))

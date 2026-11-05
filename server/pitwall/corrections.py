"""Correction overlay. A displayed value replaces the producer's, and both stay visible."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .contract import Correction, Measurement
from .util import parse_fraction


def load_corrections(path: str) -> list[dict]:
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rows = d.get("corrections") if isinstance(d, dict) else None
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def apply_fraction(
    corrections: list[dict],
    task_id: str,
    field: str,
    producer: Measurement,
    read_at: str,
) -> tuple[Measurement, list[Correction]]:
    """Return (measurement to display, corrections applied). Without a matching row the producer value is returned."""
    for row in corrections:
        if row.get("task_id") != task_id or row.get("field") != field:
            continue
        num, den = row.get("numerator"), row.get("denominator")
        if not isinstance(num, int) or not isinstance(den, int):
            parsed = parse_fraction(row.get("displayed_value"))
            if not parsed:
                continue
            num, den = parsed
        shown = Measurement(
            value=f"{num}/{den}", unit="facts", observed_at=None, read_at=read_at,
            source="correction: " + str(row.get("source", ""))[:160], status="ok", scope="job",
            numerator=num, denominator=den,
            note=f"{num}/{den}, {row.get('basis_label', 'corrected')}; producer record: {row.get('producer_value', '')}",
        )
        corr = Correction(field=field, displayed_value=str(row.get("displayed_value", f"{num}/{den}")),
                          basis_label=str(row.get("basis_label", "")),
                          producer_value=str(row.get("producer_value", producer.value if producer.value is not None else "")),
                          source=str(row.get("source", "")), note=str(row.get("note", "")))
        return shown, [corr]
    return producer, []

"""Mtime-keyed reader for an allowlist of receipts in a task's run directory. Never opens a .duckdb file."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from ..participation import ReceiptView

# Parsed (JSON). Everything else in the directory is only listed by name and size.
PARSE_JSON = {
    "execution.json", "job-succeeded.json", "job-running.json", "job-queued.json", "submitted.json",
    "LOOKUP-MEASURE.json", "CONTEXT-DELIVERY.json", "PACK-CACHE-RECEIPTS.json", "DUCKDB-RECEIPT.json",
    "PARENT-CHECKS.json", "REVIEW-BUNDLE.json", "CHECKS.json", "consumption.json", "RESULT.json",
    "RECOVERY.json", "SUMMARY.json",
}
PARSE_JSONL = {"BROKER-RECEIPTS.jsonl", "IRC-RECEIPTS.jsonl"}
MAX_PARSE_BYTES = 512 * 1024


class ReceiptReader:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._file_cache: dict[tuple[str, int, int], Any] = {}
        self._view_cache: dict[str, tuple[tuple, ReceiptView]] = {}

    def read(self, run_dir: str) -> ReceiptView:
        with self._lock:
            return self._read(run_dir)

    def _read(self, run_dir: str) -> ReceiptView:
        files: dict[str, tuple[int, int]] = {}
        dirs: set[str] = set()
        try:
            with os.scandir(run_dir) as it:
                for e in it:
                    try:
                        if e.is_dir(follow_symlinks=False):
                            dirs.add(e.name)
                        elif e.is_file(follow_symlinks=False):
                            st = e.stat(follow_symlinks=False)
                            files[e.name] = (st.st_mtime_ns, st.st_size)
                    except OSError:
                        continue
        except OSError:
            return ReceiptView(run_dir=run_dir)
        sig = tuple(sorted((n, m, s) for n, (m, s) in files.items())) + tuple(sorted(dirs))
        hit = self._view_cache.get(run_dir)
        if hit and hit[0] == sig:
            return hit[1]
        data: dict[str, Any] = {}
        lines: dict[str, list[dict]] = {}
        for name, (mtime, size) in files.items():
            if name in PARSE_JSON or name in PARSE_JSONL:
                if size > MAX_PARSE_BYTES:
                    continue
                key = (os.path.join(run_dir, name), mtime, size)
                if key not in self._file_cache:
                    self._file_cache[key] = self._parse(os.path.join(run_dir, name), name)
                parsed = self._file_cache[key]
                if parsed is None:
                    continue
                (lines if name in PARSE_JSONL else data)[name] = parsed
        # Bound the per-file cache.
        if len(self._file_cache) > 600:
            self._file_cache.clear()
        view = ReceiptView(run_dir=run_dir, files={n: s for n, (_, s) in files.items()}, dirs=dirs, data=data, lines=lines)
        self._view_cache[run_dir] = (sig, view)
        return view

    @staticmethod
    def _parse(path: str, name: str) -> Any:
        try:
            text = Path(path).read_text(encoding="utf-8")
            if name.endswith(".jsonl"):
                out = []
                for ln in text.splitlines():
                    ln = ln.strip()
                    if not ln:
                        continue
                    try:
                        v = json.loads(ln)
                    except ValueError:
                        continue
                    if isinstance(v, dict):
                        v.pop("raw_irc_line", None)  # never carried past the reader
                        out.append(v)
                return out
            v = json.loads(text)
            return v if isinstance(v, dict) else None
        except (OSError, ValueError):
            return None

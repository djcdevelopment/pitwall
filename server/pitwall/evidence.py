"""Evidence registry and serving rules.

Clients send task ids and record ids, never paths. Only .json .jsonl .md .png are served; deny-listed names,
anything outside PITWALL_RUN_ROOTS (realpath), and every other extension (.log, .claim, .py, .patch, .txt,
.html, .duckdb ...) are listed as not served. Text is scrubbed before it leaves the process.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from .contract import EvidenceIndex, EvidenceRecord

SERVED_EXT = {".json": "json", ".jsonl": "jsonl", ".md": "markdown", ".png": "image"}
DENY_NAME = re.compile(r"(?i)(key|secret|credential|\.env|passw)")
MAX_TEXT_BYTES = 2 * 1024 * 1024
MAX_IMAGE_BYTES = 8 * 1024 * 1024

_BEARER = re.compile(r"(?i)bearer\s+\S+")
# key names that hold a secret; plural counters such as input_tokens / max_tokens do not match
_SECRET_KEY = re.compile(
    r"(?i)(api[_-]?key|secret|authorization|passw(or)?d|credential|private[_-]?key|"
    r"(^|[_-])(access|auth|bearer|refresh|session|id|api)[_-]?token$|^token$|[_-]token$)"
)
REDACTED = "[redacted]"


def scrub_text(text: str) -> str:
    return _BEARER.sub("Bearer [redacted]", text)


def scrub_value(v: Any, key: str = "") -> Any:
    if key == "raw_irc_line":
        return REDACTED
    if key and _SECRET_KEY.search(key):
        return REDACTED
    if isinstance(v, dict):
        return {k: scrub_value(x, str(k)) for k, x in v.items()}
    if isinstance(v, list):
        return [scrub_value(x, key) for x in v]
    if isinstance(v, str):
        return scrub_text(v)
    return v


def render_text(kind: str, raw: bytes) -> str:
    text = raw.decode("utf-8", "replace")
    if kind == "json":
        try:
            return json.dumps(scrub_value(json.loads(text)), indent=2, ensure_ascii=False) + "\n"
        except ValueError:
            return scrub_text(text)
    if kind == "jsonl":
        out = []
        for ln in text.splitlines():
            if not ln.strip():
                continue
            try:
                out.append(json.dumps(scrub_value(json.loads(ln)), ensure_ascii=False))
            except ValueError:
                out.append(scrub_text(ln))
        return "\n".join(out) + "\n"
    return scrub_text(text)


def record_id_for(relpath: str) -> str:
    return hashlib.sha256(relpath.encode("utf-8")).hexdigest()[:16]


@dataclass
class _Entry:
    path: str
    name: str
    kind: str
    size: int
    mtime: float


class Evidence:
    def __init__(self, run_roots: list[str]):
        self.roots = [os.path.realpath(r) for r in run_roots]
        self._lock = threading.Lock()
        self._records: dict[str, dict[str, _Entry]] = {}   # task_id -> record_id -> entry
        self._not_served: dict[str, list[str]] = {}
        self._extra_roots: set[str] = set()

    def _root_for(self, real: str, allow_extra: bool) -> Optional[str]:
        for r in self.roots + (sorted(self._extra_roots) if allow_extra else []):
            if real == r or real.startswith(r.rstrip("/") + "/"):
                return r
        return None

    def refresh(self, tasks: list[tuple[str, str]]) -> dict[str, dict[str, str]]:
        """Rescan run directories for the tasks flow-top reports. Returns task_id -> {file name -> record_id}."""
        records: dict[str, dict[str, _Entry]] = {}
        not_served: dict[str, list[str]] = {}
        names: dict[str, dict[str, str]] = {}
        extra: set[str] = set()
        for task_id, run_dir in tasks:
            if not run_dir:
                continue
            real_dir = os.path.realpath(run_dir)
            # Washplant run directories are allowed only because flow-top reports one for a task.
            if "washplant" in real_dir.split(os.sep) and os.path.isdir(real_dir):
                extra.add(real_dir)
        with self._lock:
            self._extra_roots = extra
        for task_id, run_dir in tasks:
            recs: dict[str, _Entry] = {}
            skipped: list[str] = []
            nmap: dict[str, str] = {}
            real_dir = os.path.realpath(run_dir) if run_dir else ""
            root = self._root_for(real_dir, True) if real_dir else None
            if root and os.path.isdir(real_dir):
                try:
                    entries = sorted(os.scandir(real_dir), key=lambda e: e.name)
                except OSError:
                    entries = []
                for e in entries:
                    try:
                        if e.is_dir(follow_symlinks=False):
                            skipped.append(e.name + "/")
                            continue
                        if not e.is_file(follow_symlinks=False):
                            skipped.append(e.name)
                            continue
                        ext = os.path.splitext(e.name)[1].lower()
                        real = os.path.realpath(e.path)
                        if ext not in SERVED_EXT or DENY_NAME.search(e.name) or not self._root_for(real, True):
                            skipped.append(e.name)
                            continue
                        st = e.stat(follow_symlinks=False)
                        cap = MAX_IMAGE_BYTES if ext == ".png" else MAX_TEXT_BYTES
                        if st.st_size > cap:
                            skipped.append(e.name)
                            continue
                        rel = os.path.relpath(real, os.path.dirname(real_dir))
                        rid = record_id_for(f"{task_id}/{rel}")
                        recs[rid] = _Entry(real, e.name, SERVED_EXT[ext], st.st_size, st.st_mtime)
                        nmap[e.name] = rid
                    except OSError:
                        continue
            records[task_id] = recs
            not_served[task_id] = skipped
            names[task_id] = nmap
        with self._lock:
            self._records = records
            self._not_served = not_served
        return names

    def known(self, task_id: str) -> bool:
        with self._lock:
            return task_id in self._records

    def index(self, task_id: str) -> Optional[EvidenceIndex]:
        with self._lock:
            recs = self._records.get(task_id)
            if recs is None:
                return None
            out = [
                EvidenceRecord(
                    record_id=rid, name=e.name, kind=e.kind, bytes=e.size,  # type: ignore[arg-type]
                    modified_at=datetime.fromtimestamp(e.mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                )
                for rid, e in sorted(recs.items(), key=lambda kv: kv[1].name)
            ]
            return EvidenceIndex(task_id=task_id, records=out, not_served=list(self._not_served.get(task_id, [])))

    def content(self, task_id: str, record_id: str) -> Optional[tuple[str, bytes, str]]:
        """(media_type, body, kind) for a registered record; None if unknown or no longer safe to serve."""
        with self._lock:
            e = self._records.get(task_id, {}).get(record_id)
            extra = sorted(self._extra_roots)
        if e is None:
            return None
        real = os.path.realpath(e.path)
        if real != e.path or not any(real.startswith(r.rstrip("/") + "/") for r in self.roots + extra):
            return None
        ext = os.path.splitext(real)[1].lower()
        if ext not in SERVED_EXT or DENY_NAME.search(os.path.basename(real)):
            return None
        try:
            with open(real, "rb") as fh:
                raw = fh.read((MAX_IMAGE_BYTES if ext == ".png" else MAX_TEXT_BYTES) + 1)
        except OSError:
            return None
        if ext == ".png":
            return "image/png", raw, "image"
        if len(raw) > MAX_TEXT_BYTES:
            return None
        return "text/plain; charset=utf-8", render_text(e.kind, raw).encode("utf-8"), e.kind

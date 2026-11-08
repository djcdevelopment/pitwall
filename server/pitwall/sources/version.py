"""Read-only version of an external collector checkout. Reports the checkout's state now, which
is not necessarily the code that wrote a cached snapshot: a long-running TUI keeps what it loaded."""

from __future__ import annotations

import subprocess

from ..contract import CollectorVersion
from ..util import iso_from_epoch, scrub_identifiers


def _git(repo: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "--no-optional-locks", "-C", repo, *args], capture_output=True, text=True,
                          timeout=3, stdin=subprocess.DEVNULL, check=False)


def read_version(repo: str, now: float) -> CollectorVersion:
    base = {"repo": scrub_identifiers(repo), "checked_at": iso_from_epoch(now) or ""}
    try:
        head = _git(repo, "rev-parse", "HEAD")
        if head.returncode != 0:
            return CollectorVersion(**base, note="Not a git checkout: no commit or dirty state can be recorded.")
        status = _git(repo, "status", "--porcelain")
        if status.returncode != 0:
            return CollectorVersion(**base, commit=head.stdout.strip(), note="git status failed: dirty state unknown.")
    except (OSError, subprocess.SubprocessError) as exc:
        return CollectorVersion(**base, note=scrub_identifiers(f"git unavailable: {exc}"))
    changed = [line[3:] for line in status.stdout.splitlines() if line[3:]]
    return CollectorVersion(**base, commit=head.stdout.strip(), dirty=bool(changed), changed_files=changed[:40],
                            note="Checkout state now. A cached snapshot may come from a process that loaded earlier code.")

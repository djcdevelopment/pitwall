"""python -m pitwall: bind 127.0.0.1 only. Aborts, naming the next free port, if the port is busy."""

from __future__ import annotations

import socket
import sys

import uvicorn

from .app import create_app
from .config import load


def _free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # same as uvicorn: lingering TIME_WAIT is not 'busy'
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def main() -> int:
    cfg = load()
    if not _free(cfg.host, cfg.port):
        nxt = next((p for p in range(cfg.port + 1, cfg.port + 50) if _free(cfg.host, p)), None)
        print(f"pitwall: {cfg.host}:{cfg.port} is busy; not touching its owner. Next free port: {nxt} (set PITWALL_PORT).", file=sys.stderr)
        return 2
    uvicorn.run(create_app(cfg), host=cfg.host, port=cfg.port, log_level="warning", access_log=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Signal daemon to reload its in-memory matcher."""
from __future__ import annotations

import logging
import os
import signal
from pathlib import Path

PID_FILE = Path("/run/smart-gate/pid")
log = logging.getLogger(__name__)


def signal_daemon() -> None:
    if not PID_FILE.exists():
        log.info("daemon not running; matcher will load fresh next start")
        return
    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, signal.SIGUSR1)
    except (ProcessLookupError, PermissionError, ValueError) as e:
        log.warning("could not signal daemon: %s", e)

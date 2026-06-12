"""Tests for the Flask thread bootstrap in smart_gate.main.

`_run_web` runs as a daemon thread. If the configured port is already in
use, werkzeug's `make_server` historically printed to stderr and called
`sys.exit(1)`, which only killed the Flask thread — the daemon kept
running with the web UI dead.  The thread must instead trigger a full
process shutdown so systemd restarts the unit and operators are alerted.
"""
from __future__ import annotations

import socket
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from smart_gate import main as main_mod


def test_run_web_sets_shutdown_on_port_in_use():
    """A pre-bound port forces EADDRINUSE; _run_web must set the shutdown event."""
    # Bind a free port so the second bind in _run_web hits EADDRINUSE.
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 0))
        host, port = s.getsockname()
        s.listen(1)

        cfg = SimpleNamespace(web=SimpleNamespace(host=host, port=port))
        shutdown = threading.Event()

        # create_app is heavy and pulls in DB/hub wiring we don't need here.
        with patch.object(main_mod, "create_app", return_value=MagicMock()):
            main_mod._run_web(
                cfg,
                db=None,
                hub=None,
                uart=None,
                data_dir=None,
                shutdown=shutdown,
            )

        assert shutdown.is_set(), (
            "Port-in-use must trigger full daemon shutdown so systemd restarts"
        )
    finally:
        s.close()

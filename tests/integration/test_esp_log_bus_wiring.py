import queue
import threading
import time
from unittest.mock import MagicMock
from smart_gate.data.db import Database
from smart_gate.link.esp_log_bus import EspLogBus
from smart_gate.link.uart_client import EspEvent


def test_log_event_publishes_to_bus(tmp_data_dir):
    """When _consume_bus processes an EspEvent v='log', it should both
    INSERT into esp_log and publish to the bus.

    Note: as of Task 2.4 the published bus payload no longer carries a DB
    `id` field — writes are batched via EspLogWriter, so the row id is not
    known synchronously. The SSE formatter handles the absent-id case the
    same way it handles synthetic audit events.
    """
    from smart_gate.main import _consume_bus

    db = Database(tmp_data_dir / "w.db"); db.migrate()
    bus_log = EspLogBus()
    in_q: queue.Queue = queue.Queue()
    out_trig: queue.Queue = queue.Queue()
    shutdown = threading.Event()
    reload_evt = threading.Event()

    sub = bus_log.subscribe()

    # Fake config object with the attributes _consume_bus reads.
    class _Cfg:
        class recognition:
            stranger_cooldown_s = 30.0
    cfg = _Cfg()

    # Start the consumer thread. Current _consume_bus signature is
    # (bus, db, matcher, uart, trig_queue, cfg, shutdown, reload_event,
    #  *, auto_enroll_state=None, gate_tracker=None, esp_log_bus=None,
    #  peripherals=None)
    t = threading.Thread(
        target=_consume_bus,
        args=(in_q, db, MagicMock(), MagicMock(), out_trig, cfg,
              shutdown, reload_evt),
        kwargs={"auto_enroll_state": None, "gate_tracker": None,
                "esp_log_bus": bus_log, "peripherals": None},
        daemon=True,
    )
    t.start()

    in_q.put(EspEvent(v="log",
                      data={"lvl": "info", "tag": "rfid", "msg": "uid granted"}))

    item = bus_log.wait_for_item(sub, timeout=1.0)
    shutdown.set(); t.join(timeout=1.0)

    assert item is not None
    assert item["lvl"] == "info"
    assert item["tag"] == "rfid"
    assert item["msg"] == "uid granted"
    # id is optional now (absent for batched + synthetic log events).
    assert item.get("id") is None or isinstance(item["id"], int)
    # DB row insertion path: this test doesn't wire EspLogWriter so
    # _handle_esp_event falls back to the synchronous db.insert_esp_log.
    rows = db.recent_esp_log(limit=10)
    assert len(rows) == 1
    assert rows[0][4] == "uid granted"

import threading
import time
from smart_gate.link.esp_log_bus import EspLogBus


def test_subscribe_publish_receive():
    bus = EspLogBus()
    q = bus.subscribe()
    bus.publish({"id": 1, "msg": "hi"})
    item = bus.wait_for_item(q, timeout=0.5)
    assert item == {"id": 1, "msg": "hi"}


def test_multiple_subscribers_receive():
    bus = EspLogBus()
    q1, q2 = bus.subscribe(), bus.subscribe()
    bus.publish({"id": 1})
    assert bus.wait_for_item(q1, timeout=0.5) == {"id": 1}
    assert bus.wait_for_item(q2, timeout=0.5) == {"id": 1}


def test_overflow_drops_oldest():
    bus = EspLogBus(queue_cap=3)
    q = bus.subscribe()
    for i in range(5):
        bus.publish({"id": i})
    items = []
    while True:
        item = bus.wait_for_item(q, timeout=0.05)
        if item is None:
            break
        items.append(item)
    # deque(maxlen=3) keeps last 3 publishes
    assert [i["id"] for i in items] == [2, 3, 4]


def test_unsubscribe_removes_subscriber():
    bus = EspLogBus()
    q = bus.subscribe()
    assert bus.subscriber_count() == 1
    bus.unsubscribe(q)
    assert bus.subscriber_count() == 0


def test_wait_for_item_timeout_returns_none():
    bus = EspLogBus()
    q = bus.subscribe()
    item = bus.wait_for_item(q, timeout=0.05)
    assert item is None


def test_wait_unblocks_on_publish():
    bus = EspLogBus()
    q = bus.subscribe()
    received = []

    def reader():
        received.append(bus.wait_for_item(q, timeout=1.0))

    t = threading.Thread(target=reader)
    t.start()
    time.sleep(0.05)
    bus.publish({"id": 42})
    t.join(timeout=1.0)
    assert received == [{"id": 42}]


def test_unsubscribe_uses_identity_not_value():
    """Two empty subscribers compare equal; unsubscribe must remove by identity.

    The tricky case: when q2 is subscribed first, list.remove(q1) would find q2
    first (because empty deques are equal) and silently remove the wrong entry.
    """
    bus = EspLogBus()
    # Subscribe q2 FIRST so it sits at index 0 in the internal list.
    # list.remove(q1) with value equality would then remove q2 instead.
    q2 = bus.subscribe()
    q1 = bus.subscribe()
    assert bus.subscriber_count() == 2
    # Both q1 and q2 are empty deques; q1 == q2 is True
    assert q1 == q2
    bus.unsubscribe(q1)
    assert bus.subscriber_count() == 1
    # The remaining subscriber must be q2 (by identity), so publishing reaches it.
    bus.publish({"id": 99})
    assert bus.wait_for_item(q2, timeout=0.5) == {"id": 99}

"""Tests for TwoFactorState — pairing, TTL, consumption cooldown."""
import time

import numpy as np
import pytest

from smart_gate.recognition.two_factor import TwoFactorState


def _emb(value: float = 0.5) -> np.ndarray:
    return np.full(128, value, dtype="float32")


def test_face_alone_no_pair():
    s = TwoFactorState()
    assert s.set_face_and_try_match(_emb(), matched_user_id=None, distance=1.0) is None


def test_grant_alone_no_pair():
    s = TwoFactorState()
    assert s.set_grant_and_try_match(7, "qr") is None


def test_face_then_grant_pairs():
    s = TwoFactorState()
    s.set_face_and_try_match(_emb(), matched_user_id=None, distance=1.0)
    pair = s.set_grant_and_try_match(7, "qr")
    assert pair is not None
    assert pair.grant_user_id == 7
    assert pair.grant_source == "qr"
    assert pair.face_matched_user_id is None


def test_grant_then_face_pairs():
    s = TwoFactorState()
    s.set_grant_and_try_match(7, "rfid")
    pair = s.set_face_and_try_match(_emb(), matched_user_id=None, distance=1.0)
    assert pair is not None


def test_ttl_expiry():
    s = TwoFactorState(ttl_s=0.05)
    s.set_face_and_try_match(_emb(), matched_user_id=None, distance=1.0)
    time.sleep(0.08)
    # Grant arrives after face TTL → no pair
    assert s.set_grant_and_try_match(7, "qr") is None


def test_consumption_cooldown_blocks_repeat():
    """After a successful pair consume, further pairs are suppressed
    for `consumption_cooldown_s` seconds. Same face+QR in frame each
    frame should not refire."""
    s = TwoFactorState(consumption_cooldown_s=0.3)
    s.set_face_and_try_match(_emb(), matched_user_id=None, distance=1.0)
    first = s.set_grant_and_try_match(7, "qr")
    assert first is not None
    # Repeat immediately — both slots get refilled but cooldown blocks consume.
    s.set_face_and_try_match(_emb(), matched_user_id=None, distance=1.0)
    second = s.set_grant_and_try_match(7, "qr")
    assert second is None, "cooldown should suppress repeat consume"
    # After cooldown expires, next pair fires. Either call can return it —
    # set_face_and_try_match may produce the pair because the grant slot
    # was never cleared (consume blocked, slot kept). Accept either.
    time.sleep(0.35)
    r1 = s.set_face_and_try_match(_emb(), matched_user_id=None, distance=1.0)
    r2 = s.set_grant_and_try_match(7, "qr")
    assert r1 is not None or r2 is not None, \
        "cooldown should have released by now"


def test_consumption_cooldown_applies_per_state_not_per_user():
    """Even a different user pair is blocked during cooldown — the
    state is global, intentional (1 cmd:open per cooldown window
    no matter who scanned)."""
    s = TwoFactorState(consumption_cooldown_s=0.3)
    s.set_face_and_try_match(_emb(), matched_user_id=None, distance=1.0)
    assert s.set_grant_and_try_match(1, "qr") is not None
    s.set_face_and_try_match(_emb(0.8), matched_user_id=None, distance=1.0)
    assert s.set_grant_and_try_match(2, "rfid") is None


def test_reset_cooldown_helper():
    s = TwoFactorState(consumption_cooldown_s=10.0)
    s.set_face_and_try_match(_emb(), matched_user_id=None, distance=1.0)
    s.set_grant_and_try_match(7, "qr")
    s.reset_cooldown()
    s.set_face_and_try_match(_emb(), matched_user_id=None, distance=1.0)
    assert s.set_grant_and_try_match(7, "qr") is not None

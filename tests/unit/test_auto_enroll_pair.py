import time
import numpy as np
import pytest

from smart_gate.recognition.auto_enroll_pair import (
    AutoEnrollPairState, EnrollCandidate,
)


def _fake_embedding():
    return np.zeros(128, dtype=np.float32)


def test_grant_then_face_within_ttl_returns_candidate_when_face_unmatched():
    s = AutoEnrollPairState(ttl_s=4.0)
    assert s.set_grant_and_wait_for_face(user_id=7, source="rfid") is None
    cand = s.set_face_seen(embedding=_fake_embedding(),
                          matched_user_id=None, distance=1.0)
    assert isinstance(cand, EnrollCandidate)
    assert cand.grant_user_id == 7


def test_face_then_grant_within_ttl_also_returns_candidate():
    s = AutoEnrollPairState(ttl_s=4.0)
    assert s.set_face_seen(embedding=_fake_embedding(),
                          matched_user_id=None, distance=1.0) is None
    cand = s.set_grant_and_wait_for_face(user_id=7, source="rfid")
    assert isinstance(cand, EnrollCandidate)


def test_qr_grant_is_ignored():
    s = AutoEnrollPairState(ttl_s=4.0)
    s.set_face_seen(embedding=_fake_embedding(),
                    matched_user_id=None, distance=1.0)
    assert s.set_grant_and_wait_for_face(user_id=7, source="qr") is None


def test_face_already_matched_does_not_enroll():
    s = AutoEnrollPairState(ttl_s=4.0)
    s.set_grant_and_wait_for_face(user_id=7, source="rfid")
    cand = s.set_face_seen(embedding=_fake_embedding(),
                          matched_user_id=5, distance=0.18)
    assert cand is None


def test_stale_grant_does_not_pair():
    s = AutoEnrollPairState(ttl_s=0.1)
    s.set_grant_and_wait_for_face(user_id=7, source="rfid")
    time.sleep(0.2)
    cand = s.set_face_seen(embedding=_fake_embedding(),
                          matched_user_id=None, distance=1.0)
    assert cand is None


def test_pair_consumes_slots():
    s = AutoEnrollPairState(ttl_s=4.0)
    s.set_grant_and_wait_for_face(user_id=7, source="rfid")
    cand1 = s.set_face_seen(embedding=_fake_embedding(),
                           matched_user_id=None, distance=1.0)
    assert cand1 is not None
    # Second face after consume — no pair until a fresh grant
    cand2 = s.set_face_seen(embedding=_fake_embedding(),
                           matched_user_id=None, distance=1.0)
    assert cand2 is None

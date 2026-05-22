import numpy as np
import pytest
from smart_gate.data.db import Database
from smart_gate.recognition.matcher import Matcher


@pytest.fixture
def db(tmp_path):
    d = Database(tmp_path / "m.db")
    d.migrate()
    return d


def _embed(value: float) -> bytes:
    return np.full(128, value, dtype="float32").tobytes()


def test_empty_index_no_match(db):
    m = Matcher(db)
    user_id, dist = m.match_face(np.full(128, 0.5, dtype="float32"))
    assert user_id is None
    assert dist == float("inf")


def test_single_sample_match(db):
    uid = db.insert_user("alice")
    db.insert_face_encoding(uid, _embed(0.5), 0)
    m = Matcher(db)
    user_id, dist = m.match_face(np.full(128, 0.5, dtype="float32"))
    assert user_id == uid
    assert dist == 0.0


def test_multi_sample_returns_min_distance(db):
    uid = db.insert_user("alice")
    db.insert_face_encoding(uid, _embed(0.5), 0)
    db.insert_face_encoding(uid, _embed(0.6), 1)
    m = Matcher(db)
    probe = np.full(128, 0.59, dtype="float32")
    user_id, dist = m.match_face(probe)
    assert user_id == uid
    expected_far = np.linalg.norm(np.full(128, 0.59) - np.full(128, 0.5))
    expected_near = np.linalg.norm(np.full(128, 0.59) - np.full(128, 0.6))
    assert abs(dist - expected_near) < 1e-4
    assert expected_near < expected_far


def test_match_picks_closest_user(db):
    uid_a = db.insert_user("alice")
    db.insert_face_encoding(uid_a, _embed(0.5), 0)
    uid_b = db.insert_user("bob")
    db.insert_face_encoding(uid_b, _embed(0.9), 0)
    m = Matcher(db)
    user_id, _ = m.match_face(np.full(128, 0.85, dtype="float32"))
    assert user_id == uid_b


def test_reload_picks_up_new_encoding(db):
    uid = db.insert_user("alice")
    db.insert_face_encoding(uid, _embed(0.5), 0)
    m = Matcher(db)
    uid_b = db.insert_user("bob")
    db.insert_face_encoding(uid_b, _embed(0.9), 0)
    probe = np.full(128, 0.9, dtype="float32")
    u, _ = m.match_face(probe)
    assert u == uid                              # stale: still alice (closest in stale index)
    m.reload(db)
    u, d = m.match_face(probe)
    assert u == uid_b
    assert d == 0.0


def test_qr_lookup(db):
    uid = db.insert_user("alice")
    db.insert_qr_token("aabbcc", uid)
    m = Matcher(db)
    assert m.lookup_qr("aabbcc") == uid
    assert m.lookup_qr("nope") is None
    db.revoke_active_qr(uid)
    m.reload(db)
    assert m.lookup_qr("aabbcc") is None

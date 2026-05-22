from datetime import datetime, timedelta
from pathlib import Path
import pytest
from smart_gate.data.db import Database
from smart_gate.video.recorder import cleanup_pass


@pytest.fixture
def db(tmp_path):
    d = Database(tmp_path / "rec.db")
    d.migrate()
    return d


def _make_event_with_clip(db, data_dir: Path, age_days: int, size_bytes: int) -> int:
    eid = db.insert_event("face", None, True)
    ts = (datetime.now() - timedelta(days=age_days)).isoformat(sep=" ", timespec="seconds")
    db.connect().execute("UPDATE events SET ts=? WHERE id=?", (ts, eid))
    db.connect().commit()
    clip_path = f"clips/{eid}.mp4"
    (data_dir / "clips").mkdir(exist_ok=True)
    (data_dir / clip_path).write_bytes(b"\0" * size_bytes)
    db.update_event_clip(eid, clip_path)
    return eid


def test_cleanup_age_only(db, tmp_data_dir):
    old = _make_event_with_clip(db, tmp_data_dir, age_days=40, size_bytes=1024)
    fresh = _make_event_with_clip(db, tmp_data_dir, age_days=5, size_bytes=1024)
    cleanup_pass(tmp_data_dir, db, max_age_days=30, max_total_gb=100)
    rows = {r[0]: r[7] for r in db.recent_events()}     # id -> clip_path
    assert rows[old] is None
    assert rows[fresh] == f"clips/{fresh}.mp4"
    assert not (tmp_data_dir / f"clips/{old}.mp4").exists()


def test_cleanup_size_only(db, tmp_data_dir):
    ids = [_make_event_with_clip(db, tmp_data_dir, age_days=1, size_bytes=500_000)
           for _ in range(3)]
    cleanup_pass(tmp_data_dir, db, max_age_days=365, max_total_gb=0.001)  # 0.001 GB = 1 MB
    rows = {r[0]: r[7] for r in db.recent_events()}
    assert rows[ids[0]] is None                          # deleted (oldest)
    remaining_bytes = sum(
        (tmp_data_dir / r[7]).stat().st_size for r in db.recent_events() if r[7]
    )
    assert remaining_bytes <= 1_000_000


def test_cleanup_hybrid(db, tmp_data_dir):
    old = _make_event_with_clip(db, tmp_data_dir, age_days=40, size_bytes=500_000)
    young_a = _make_event_with_clip(db, tmp_data_dir, age_days=2, size_bytes=600_000)
    young_b = _make_event_with_clip(db, tmp_data_dir, age_days=1, size_bytes=600_000)
    cleanup_pass(tmp_data_dir, db, max_age_days=30, max_total_gb=0.001)
    rows = {r[0]: r[7] for r in db.recent_events()}
    assert rows[old] is None
    assert rows[young_a] is None
    assert rows[young_b] == f"clips/{young_b}.mp4"


def test_cleanup_empty(db, tmp_data_dir):
    cleanup_pass(tmp_data_dir, db, max_age_days=30, max_total_gb=5)


def test_cleanup_missing_clip_file(db, tmp_data_dir):
    eid = _make_event_with_clip(db, tmp_data_dir, age_days=40, size_bytes=1000)
    (tmp_data_dir / f"clips/{eid}.mp4").unlink()
    cleanup_pass(tmp_data_dir, db, max_age_days=30, max_total_gb=5)
    rows = {r[0]: r[7] for r in db.recent_events()}
    assert rows[eid] is None

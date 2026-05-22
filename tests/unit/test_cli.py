import pytest
from smart_gate.data.db import Database
from smart_gate.cli import qr as qr_mod
from smart_gate.cli import users as users_mod
from smart_gate.cli import events as events_mod


@pytest.fixture
def db(tmp_path):
    d = Database(tmp_path / "cli.db")
    d.migrate()
    return d


def test_qr_rotate_creates_token_and_png(db, tmp_path, monkeypatch):
    db.insert_user("alice")
    monkeypatch.setattr("smart_gate.cli.qr.signal_daemon", lambda: None)
    qr_dir = tmp_path / "qr"
    path = qr_mod.rotate(db, "alice", qr_dir)
    assert path.exists()
    assert path.stat().st_size > 100
    tokens = db.load_active_qr_tokens()
    assert len(tokens) == 1


def test_qr_rotate_revokes_old(db, tmp_path, monkeypatch):
    monkeypatch.setattr("smart_gate.cli.qr.signal_daemon", lambda: None)
    db.insert_user("alice")
    qr_mod.rotate(db, "alice", tmp_path / "qr")
    qr_mod.rotate(db, "alice", tmp_path / "qr")
    tokens = db.load_active_qr_tokens()
    assert len(tokens) == 1
    n_total = db.connect().execute("SELECT COUNT(*) FROM qr_tokens").fetchone()[0]
    assert n_total == 2


def test_qr_revoke_no_user_raises(db, tmp_path, monkeypatch):
    monkeypatch.setattr("smart_gate.cli.qr.signal_daemon", lambda: None)
    with pytest.raises(SystemExit):
        qr_mod.revoke(db, "nope")


def test_users_delete_unknown_raises(db, monkeypatch):
    monkeypatch.setattr("smart_gate.cli.users.signal_daemon", lambda: None)
    with pytest.raises(SystemExit):
        users_mod.delete_user(db, "nope")


def test_users_list_prints(db, capsys, monkeypatch):
    monkeypatch.setattr("smart_gate.cli.users.signal_daemon", lambda: None)
    db.insert_user("alice")
    users_mod.list_users(db)
    out = capsys.readouterr().out
    assert "alice" in out


def test_events_tail(db, capsys):
    db.insert_user("alice")
    uid = db.get_user_id_by_name("alice")
    db.insert_event("face", uid, True, detail='{"distance":0.4}')
    events_mod.tail(db, n=10)
    out = capsys.readouterr().out
    assert "alice" in out
    assert "face" in out

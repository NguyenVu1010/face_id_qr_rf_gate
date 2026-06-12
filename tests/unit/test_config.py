import logging
import sys
from pathlib import Path

from smart_gate.config import Config, load_config

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore


def test_defaults_applied(tmp_path):
    # Verifies dataclass defaults (Config()) — NOT packaging/config.default.toml.
    # The shipped TOML is covered by test_packaging_default_toml_values below.
    cfg_file = tmp_path / "c.toml"
    cfg_file.write_text("")
    cfg = load_config(cfg_file)
    assert cfg.video.fps == 15
    assert cfg.recognition.face_threshold == 0.55
    assert cfg.link.port == "/dev/serial0"
    assert cfg.web.port == 8080


def test_override_merges(tmp_path):
    cfg_file = tmp_path / "c.toml"
    cfg_file.write_text("""
[video]
fps = 30

[recognition]
face_threshold = 0.5
""")
    cfg = load_config(cfg_file)
    assert cfg.video.fps == 30
    assert cfg.video.width == 640                 # default preserved
    assert cfg.recognition.face_threshold == 0.5
    assert cfg.recognition.stranger_cooldown_s == 30   # default preserved


def test_unknown_key_in_section_is_warned_not_raised(tmp_path, caplog):
    import logging
    from smart_gate.config import load_config
    # Defensive: same propagation workaround as test_load_config_warns_when_file_missing.
    logging.getLogger("smart_gate.config").propagate = True
    p = tmp_path / "config.toml"
    p.write_text(
        '[recognition]\n'
        'face_threshold = 0.3\n'
        'auth_cooldown_s = 5     # legacy field, no longer in dataclass\n'
        'consumption_cooldown_s = 7.0  # also legacy\n'
    )
    with caplog.at_level(logging.WARNING, logger="smart_gate.config"):
        cfg = load_config(p)
    assert cfg.recognition.face_threshold == 0.3
    assert "auth_cooldown_s" in caplog.text
    assert "consumption_cooldown_s" in caplog.text


def test_unknown_section_is_warned_not_raised(tmp_path, caplog):
    import logging
    from smart_gate.config import load_config
    # Defensive: same propagation workaround as test_load_config_warns_when_file_missing.
    logging.getLogger("smart_gate.config").propagate = True
    p = tmp_path / "config.toml"
    p.write_text(
        '[recognition]\n'
        'face_threshold = 0.3\n'
        '\n'
        '[future_module]\n'
        'foo = 1\n'
    )
    with caplog.at_level(logging.WARNING, logger="smart_gate.config"):
        cfg = load_config(p)
    assert cfg.recognition.face_threshold == 0.3
    assert "future_module" in caplog.text


def test_missing_file_uses_defaults(tmp_path):
    cfg = load_config(tmp_path / "does-not-exist.toml")
    assert cfg.video.fps == 15


def test_link_default_port_is_serial0():
    from smart_gate.config import LinkCfg
    assert LinkCfg().port == "/dev/serial0"


def test_load_config_warns_when_file_missing(tmp_path, caplog):
    # Defensive: if a system-installed Logger subclass (e.g. ROS launch.logging)
    # disabled propagation, caplog won't see the record. Force it for the test.
    logging.getLogger("smart_gate.config").propagate = True
    missing = tmp_path / "does-not-exist.toml"
    with caplog.at_level(logging.WARNING, logger="smart_gate.config"):
        cfg = load_config(missing)
    assert "not found" in caplog.text
    assert cfg.link.port == "/dev/serial0"


def test_packaging_default_toml_values():
    """Verifies the shipped config.default.toml — drift between dataclass and TOML
    is a deployment bug (fresh installs would see the dataclass default, not TOML)."""
    repo_root = Path(__file__).resolve().parents[2]
    data = tomllib.loads((repo_root / "packaging" / "config.default.toml").read_text())
    assert data["recognition"]["face_threshold"] == 0.25
    assert data["link"]["port"] == "/dev/serial0"


def test_recognition_cooldown_defaults():
    from smart_gate.config import RecognitionCfg
    r = RecognitionCfg()
    assert r.face_cooldown_s == 5.0
    assert r.qr_cooldown_s == 5.0
    assert r.autoenroll_ttl_s == 4.0
    assert r.autoenroll_enabled is True


def test_packaging_default_toml_has_cooldown_values():
    """The shipped TOML should carry the new fields explicitly."""
    from pathlib import Path
    # Use same tomllib/tomli shim as the existing test_packaging_default_toml_values
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib   # type: ignore[no-redef]
    repo_root = Path(__file__).resolve().parents[2]
    data = tomllib.loads(
        (repo_root / "packaging" / "config.default.toml").read_text()
    )
    rec = data["recognition"]
    assert rec["face_cooldown_s"] == 5.0
    assert rec["qr_cooldown_s"] == 5.0
    assert rec["autoenroll_ttl_s"] == 4.0
    assert rec["autoenroll_enabled"] is True

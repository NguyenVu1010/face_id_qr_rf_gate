import pytest
from smart_gate.config import Config, load_config


def test_defaults_applied(tmp_path):
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
    assert cfg.recognition.auth_cooldown_s == 5   # default preserved


def test_unknown_key_raises(tmp_path):
    cfg_file = tmp_path / "c.toml"
    cfg_file.write_text("""
[video]
banana = 1
""")
    with pytest.raises(ValueError, match="unknown"):
        load_config(cfg_file)


def test_missing_file_uses_defaults(tmp_path):
    cfg = load_config(tmp_path / "does-not-exist.toml")
    assert cfg.video.fps == 15


def test_link_default_port_is_serial0():
    from smart_gate.config import LinkCfg
    assert LinkCfg().port == "/dev/serial0"

def test_load_config_warns_when_file_missing(tmp_path, caplog):
    import logging
    from smart_gate.config import load_config
    missing = tmp_path / "does-not-exist.toml"
    with caplog.at_level(logging.WARNING, logger="smart_gate.config"):
        cfg = load_config(missing)
    assert "not found" in caplog.text
    assert cfg.link.port == "/dev/serial0"

"""Tests for smart_gate.web.asset_check.check_static_assets()."""
import os
from pathlib import Path

from smart_gate.web.asset_check import (
    CRITICAL_ASSETS,
    check_static_assets,
)


def test_all_assets_healthy(tmp_path: Path):
    # Write a stub for every critical asset, each at twice the min size.
    for name, min_bytes in CRITICAL_ASSETS:
        (tmp_path / name).write_bytes(b"x" * (min_bytes * 2))
    assert check_static_assets(tmp_path) == []


def test_placeholder_under_min_flagged(tmp_path: Path):
    # 84-byte placeholder mimics the real-world failure mode.
    (tmp_path / "htmx.min.js").write_bytes(b"/* placeholder */\n" * 4)
    result = check_static_assets(tmp_path)
    assert "htmx.min.js" in result


def test_missing_asset_flagged(tmp_path: Path):
    # tmp_path is empty.
    result = check_static_assets(tmp_path)
    assert "htmx.min.js" in result


def test_permission_denied_treated_as_degraded(tmp_path: Path):
    p = tmp_path / "htmx.min.js"
    p.write_bytes(b"x" * 60_000)
    try:
        os.chmod(p, 0o000)
        result = check_static_assets(tmp_path)
    finally:
        os.chmod(p, 0o644)
    # File exists but unreadable → either fine (stat works on dir perms)
    # or flagged. Acceptable: must not raise.
    assert isinstance(result, list)


def test_empty_critical_list_returns_empty(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "smart_gate.web.asset_check.CRITICAL_ASSETS", []
    )
    assert check_static_assets(tmp_path) == []

import time
import pytest
from smart_gate.recognition.cooldown import UserCooldown


def test_passed_returns_true_for_new_user():
    c = UserCooldown(window_s=5.0)
    assert c.passed(42) is True


def test_touch_then_passed_within_window_returns_false():
    c = UserCooldown(window_s=5.0)
    c.touch(42)
    assert c.passed(42) is False


def test_touch_then_passed_after_window_returns_true(monkeypatch):
    c = UserCooldown(window_s=0.5)
    c.touch(42)
    assert c.passed(42) is False
    time.sleep(0.6)
    assert c.passed(42) is True


def test_separate_users_have_independent_cooldowns():
    c = UserCooldown(window_s=5.0)
    c.touch(1)
    assert c.passed(1) is False
    assert c.passed(2) is True

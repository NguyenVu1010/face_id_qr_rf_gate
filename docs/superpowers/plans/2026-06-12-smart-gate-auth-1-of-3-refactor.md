# Smart-gate auth refactor (1-of-3) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Make face, QR, and RFID each independently open the gate; keep auto-enroll bounded to the RFID→face pairing path only.

**Architecture:** Replace `TwoFactorState` with two narrower components — a `UserCooldown` for per-channel rate-limiting and an `AutoEnrollPairState` for RFID-only auto-enroll. Detector and `_handle_checkin` get per-channel paths.

**Spec:** `docs/superpowers/specs/2026-06-12-smart-gate-auth-1-of-3-refactor-design.md`

Inserts as **Phase 1.5** between P1 and P2 of `docs/superpowers/plans/2026-06-12-smart-gate-hang-and-robustness-fixes.md`.

---

## Task 1.5.1: `UserCooldown` primitive

**Files:**
- Create: `smart_gate/recognition/cooldown.py`
- Test: `tests/unit/test_cooldown.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_cooldown.py`:

```python
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
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
pytest tests/unit/test_cooldown.py -v
```

Expected: ImportError (module doesn't exist yet).

- [ ] **Step 3: Implement `UserCooldown`**

Create `smart_gate/recognition/cooldown.py`:

```python
"""Per-user cooldown helper for gate-open rate limiting.

A single instance tracks the last `touch()` time per user_id and answers
`passed(user_id)` based on a configurable window. Used by the detector to
suppress repeated CheckInEvents while a user stays in frame.

Not thread-safe — current callers (detector frame loop, bus consumer) run
from a single thread per channel. If that changes, wrap the dict in a Lock.
"""
from __future__ import annotations

import time


class UserCooldown:
    def __init__(self, window_s: float):
        self._window_s = window_s
        self._last: dict[int, float] = {}

    def passed(self, user_id: int) -> bool:
        last = self._last.get(user_id)
        if last is None:
            return True
        return (time.monotonic() - last) >= self._window_s

    def touch(self, user_id: int) -> None:
        self._last[user_id] = time.monotonic()
```

- [ ] **Step 4: Tests pass**

```bash
pytest tests/unit/test_cooldown.py -v
```

- [ ] **Step 5: Commit**

```bash
git add smart_gate/recognition/cooldown.py tests/unit/test_cooldown.py
git commit -m "feat(recognition): UserCooldown primitive for per-channel rate limiting

Single-thread cooldown (dict[user_id, last_touch_monotonic]); used by face
and QR channels to suppress per-frame CheckInEvent spam while the user
stays in frame.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 1.5.2: `AutoEnrollPairState` module

**Files:**
- Create: `smart_gate/recognition/auto_enroll_pair.py`
- Test: `tests/unit/test_auto_enroll_pair.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_auto_enroll_pair.py`:

```python
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
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
pytest tests/unit/test_auto_enroll_pair.py -v
```

- [ ] **Step 3: Implement `AutoEnrollPairState`**

Create `smart_gate/recognition/auto_enroll_pair.py`:

```python
"""RFID-only auto-enroll pairing.

Holds the most recent unmatched face and the most recent RFID grant. When
both are fresh (within `ttl_s`) AND the face is currently unmatched in the
encoding DB, returns an `EnrollCandidate` so the daemon can insert a new
face encoding under the RFID grant's user_id.

This is NOT the gate-open path — gate-open happens independently via the
face / QR / RFID channel routers in detector.py and main.py. This module
only handles the "tap card, look at camera → system learns face" UX.

QR grants are silently ignored (per 2026-06-12 design decision).
"""
from __future__ import annotations

import dataclasses
import threading
import time
from typing import Optional

import numpy as np


@dataclasses.dataclass(frozen=True)
class _PendingFace:
    embedding: np.ndarray
    matched_user_id: Optional[int]
    distance: float
    ts_mono: float


@dataclasses.dataclass(frozen=True)
class _PendingGrant:
    user_id: int
    ts_mono: float


@dataclasses.dataclass(frozen=True)
class EnrollCandidate:
    embedding: np.ndarray
    grant_user_id: int
    face_distance: float


class AutoEnrollPairState:
    def __init__(self, ttl_s: float = 4.0):
        self._ttl_s = ttl_s
        self._lock = threading.Lock()
        self._face: Optional[_PendingFace] = None
        self._grant: Optional[_PendingGrant] = None

    def set_face_seen(self, embedding: np.ndarray,
                      matched_user_id: Optional[int],
                      distance: float) -> Optional[EnrollCandidate]:
        with self._lock:
            self._face = _PendingFace(
                embedding=embedding,
                matched_user_id=matched_user_id,
                distance=distance,
                ts_mono=time.monotonic(),
            )
            return self._try_pair_locked()

    def set_grant_and_wait_for_face(self, user_id: int, source: str
                                    ) -> Optional[EnrollCandidate]:
        if source != "rfid":
            return None
        with self._lock:
            self._grant = _PendingGrant(user_id=user_id,
                                        ts_mono=time.monotonic())
            return self._try_pair_locked()

    def clear(self) -> None:
        with self._lock:
            self._face = None
            self._grant = None

    def _try_pair_locked(self) -> Optional[EnrollCandidate]:
        f, g = self._face, self._grant
        if f is None or g is None:
            return None
        now = time.monotonic()
        if now - f.ts_mono > self._ttl_s or now - g.ts_mono > self._ttl_s:
            return None
        if f.matched_user_id is not None:
            # Face already enrolled — don't double-enroll. Don't clear slots
            # either; a fresh unmatched face could arrive within the window.
            return None
        cand = EnrollCandidate(
            embedding=f.embedding,
            grant_user_id=g.user_id,
            face_distance=f.distance,
        )
        # Consume both slots so the same physical action doesn't enroll twice.
        self._face = None
        self._grant = None
        return cand
```

- [ ] **Step 4: Tests pass**

```bash
pytest tests/unit/test_auto_enroll_pair.py -v
```

- [ ] **Step 5: Commit**

```bash
git add smart_gate/recognition/auto_enroll_pair.py tests/unit/test_auto_enroll_pair.py
git commit -m "feat(recognition): AutoEnrollPairState — RFID-only auto-enroll pairing

Replaces the gate-open role of TwoFactorState (deleted in a later task).
Only RFID grants enter the grant slot; QR is silently ignored. Returns
EnrollCandidate only when face is currently unmatched.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 1.5.3: Config + default TOML

**Files:**
- Modify: `smart_gate/config.py`
- Modify: `packaging/config.default.toml`
- Test: `tests/unit/test_config.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/unit/test_config.py`:

```python
def test_recognition_cooldown_defaults():
    from smart_gate.config import RecognitionCfg
    r = RecognitionCfg()
    assert r.face_cooldown_s == 5.0
    assert r.qr_cooldown_s == 5.0
    assert r.autoenroll_ttl_s == 4.0
    assert r.autoenroll_enabled is True


def test_packaging_default_toml_has_cooldown_values():
    """The shipped TOML should carry the new fields explicitly."""
    import tomllib  # or 'import tomli as tomllib' on 3.10
    from pathlib import Path
    repo_root = Path(__file__).resolve().parents[2]
    data = tomllib.loads(
        (repo_root / "packaging" / "config.default.toml").read_text()
    )
    rec = data["recognition"]
    assert rec["face_cooldown_s"] == 5.0
    assert rec["qr_cooldown_s"] == 5.0
    assert rec["autoenroll_ttl_s"] == 4.0
    assert rec["autoenroll_enabled"] is True
```

(Adapt tomllib import to match what existing `test_packaging_default_toml_values` does — that fixture was added in Task 1.1.)

- [ ] **Step 2: Run tests to confirm failure**

```bash
pytest tests/unit/test_config.py -k "cooldown" -v
```

- [ ] **Step 3: Add fields to `RecognitionCfg` in `smart_gate/config.py`**

Locate `RecognitionCfg` dataclass. Append:

```python
@dataclass
class RecognitionCfg:
    # ... existing fields unchanged ...
    face_cooldown_s: float = 5.0
    qr_cooldown_s: float = 5.0
    autoenroll_ttl_s: float = 4.0
    autoenroll_enabled: bool = True
```

The existing TOML merge layer iterates declared dataclass fields, so the new fields are picked up automatically when present in `[recognition]`. If the merge layer special-cases unknown fields (e.g., `consumption_cooldown_s`), confirm it just ignores them.

- [ ] **Step 4: Append to `packaging/config.default.toml`**

Find the `[recognition]` section and add:

```toml
face_cooldown_s = 5.0       # per-user cooldown between face-alone gate opens
qr_cooldown_s = 5.0         # per-user cooldown between QR-alone gate opens
autoenroll_ttl_s = 4.0      # window after RFID grant in which an unmatched face auto-enrolls
autoenroll_enabled = true   # set false to disable the tap-card-then-look-at-camera enroll UX
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/unit/test_config.py -v
```

- [ ] **Step 6: Commit**

```bash
git add smart_gate/config.py packaging/config.default.toml tests/unit/test_config.py
git commit -m "feat(config): cooldown + auto-enroll fields for the 1-of-3 auth model

face_cooldown_s and qr_cooldown_s default to 5s; autoenroll_ttl_s
inherits the prior TwoFactorState ttl_s = 4s. autoenroll_enabled
defaults true (matches current UX of tap-card-then-look-at-camera).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 1.5.4: Detector refactor — face-alone and QR-alone gate-open paths

**Files:**
- Modify: `smart_gate/recognition/detector.py`

- [ ] **Step 1: Read existing detector frame loop**

```bash
grep -n 'set_face_and_try_match\|set_grant_and_try_match\|CheckInEvent\|state\.' smart_gate/recognition/detector.py
```

The existing pattern uses `state.set_face_and_try_match(...)` and `state.set_grant_and_try_match(qr_user_id, "qr")`. Both go away.

- [ ] **Step 2: Add a failing test in `tests/unit/test_main_bus.py`** (the file gets the integration coverage)

Add:

```python
def test_face_alone_fires_checkin_when_match_below_threshold(monkeypatch, tmp_path):
    """Face match alone — no card, no QR — should enqueue a CheckInEvent."""
    # Set up a Detector with a faked Matcher that returns (user_id=42, distance=0.18)
    # for any frame. Pump one frame, verify queue contains CheckInEvent(method="face").
    # Detailed fixture wiring left to the implementer.
    pass


def test_qr_alone_fires_checkin(...):
    pass
```

(Stubs above — implementer will flesh out using whatever fixtures `test_main_bus.py` already provides.)

- [ ] **Step 3: Replace the body of the frame-handler in `detector.py`**

Locate the section after the matcher call:

```python
# OLD (delete):
pair_from_face = state.set_face_and_try_match(embedding, matched_user_id, distance)
if pair_from_face is not None:
    bus.put(_pair_to_event(pair_from_face))
```

Replace with:

```python
# NEW:
if matched_user_id is not None and distance < cfg.recognition.face_threshold:
    if face_cooldown.passed(matched_user_id):
        face_cooldown.touch(matched_user_id)
        bus.put(CheckInEvent(
            method="face",
            user_id=matched_user_id,
            face_distance=distance,
        ))

# Auto-enroll signal — fires only if a fresh RFID grant is pending.
auto_enroll_state.set_face_seen(
    embedding=embedding,
    matched_user_id=matched_user_id,
    distance=distance,
)
```

For QR:

```python
# OLD:
pair_from_qr = state.set_grant_and_try_match(qr_user_id, "qr")
if pair_from_qr is not None:
    bus.put(_pair_to_event(pair_from_qr))

# NEW:
if qr_user_id is not None:
    if qr_cooldown.passed(qr_user_id):
        qr_cooldown.touch(qr_user_id)
        bus.put(CheckInEvent(
            method="qr",
            user_id=qr_user_id,
        ))
# Intentionally no auto-enroll call for QR.
```

- [ ] **Step 4: Update `CheckInEvent` dataclass**

In whatever module defines it (likely `smart_gate/recognition/detector.py` or a shared events module — find via `grep -rn "class CheckInEvent" smart_gate/`):

```python
@dataclass(frozen=True)
class CheckInEvent:
    method: str                    # "face" | "qr" | "rfid"
    user_id: int
    face_distance: float | None = None     # face only
    raw_uid: str | None = None             # rfid only
    qr_token: str | None = None            # qr only
```

Delete the legacy `face_embedding`, `face_matched_user_id`, `grant_user_id`, `grant_source` fields.

- [ ] **Step 5: Thread `face_cooldown`, `qr_cooldown`, `auto_enroll_state` into the detector's signature**

The detector's `run_detector` (or similar entry) currently receives `state: TwoFactorState`. Replace that single argument with three: `face_cooldown`, `qr_cooldown`, `auto_enroll_state`. The caller in `main.py` is fixed in Task 1.5.5.

- [ ] **Step 6: Tests pass + smoke import**

```bash
pytest tests/unit/test_main_bus.py -v
python -c "import smart_gate.recognition.detector"
```

- [ ] **Step 7: Commit**

```bash
git add smart_gate/recognition/detector.py tests/unit/test_main_bus.py
git commit -m "refactor(detector): face-alone + QR-alone fire CheckInEvent directly

Each channel now bypasses the old 2FA pair and goes straight to the bus
with a per-user cooldown. Auto-enroll signal kept for face frames so the
RFID pair path can still learn faces.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 1.5.5: `main.py` refactor — `_handle_checkin` + RFID handler + init wiring

**Files:**
- Modify: `smart_gate/main.py`
- Test: `tests/unit/test_main_bus.py`

- [ ] **Step 1: Add failing tests in `tests/unit/test_main_bus.py`**

```python
def test_handle_checkin_face_method_writes_event_and_sends_cmd_open(monkeypatch):
    """method=face → db.insert_event(method='face', granted=True) AND uart.send_cmd('open', ...)"""
    pass


def test_handle_checkin_qr_method_writes_event_and_sends_cmd_open():
    pass


def test_handle_checkin_rfid_method_writes_event_but_does_not_send_cmd_open():
    """ESP already opened the gate; Pi must not duplicate."""
    pass


def test_rfid_evt_creates_event_row_and_seeds_auto_enroll_when_enabled():
    """evt:rfid granted=true → bus gets CheckInEvent(method='rfid') and
       auto_enroll_state.set_grant_and_wait_for_face('rfid', user_id) is called."""
    pass


def test_rfid_evt_skips_auto_enroll_when_disabled(monkeypatch):
    """cfg.recognition.autoenroll_enabled=False → set_grant_and_wait_for_face not called."""
    pass
```

(Flesh out using existing fixtures from the file.)

- [ ] **Step 2: Rewrite `_handle_checkin` in `main.py`**

Find current `_handle_checkin` (around line 280-340). Replace body with:

```python
def _handle_checkin(evt, db, matcher, uart, trig_queue, cfg,
                   last_grant, reload_event, esp_log_bus):
    name = db.get_user_name(evt.user_id)
    if name is None:
        _audit(esp_log_bus, "warn", evt.method,
               f"unknown user_id={evt.user_id}")
        return

    detail = (f"distance={evt.face_distance:.3f}" if evt.face_distance is not None
              else evt.raw_uid if evt.raw_uid is not None
              else evt.qr_token)
    db.insert_event(method=evt.method, name=name, granted=True, detail=detail)

    # RFID is already opened by ESP — do not send cmd:open again.
    if evt.method != "rfid":
        ack = uart.send_cmd("open", {"user": name, "reason": evt.method},
                            timeout=2.0)
        if ack is None:
            _audit(esp_log_bus, "warn", evt.method,
                   f"cmd:open ack timeout user={name}")

    _audit(esp_log_bus, "info", evt.method,
           f"open user={name}")
    last_grant.set(name, evt.method)
```

(`last_grant.set` and the exact signature of `db.insert_event` may differ — adapt to actual code by reading once.)

- [ ] **Step 3: Rewrite the `evt:rfid` granted branch in `_handle_esp_event`**

Find around line 408 (current `state.set_grant_and_try_match(uid, "rfid")`). Replace with:

```python
# ESP has already opened the gate via its allowlist shortcut.
# We mirror the event row + offer to auto-enroll.
bus.put(CheckInEvent(method="rfid", user_id=uid, raw_uid=raw_uid))
if cfg.recognition.autoenroll_enabled:
    enroll = auto_enroll_state.set_grant_and_wait_for_face(uid, "rfid")
    if enroll is not None:
        _trigger_auto_enroll(enroll, db, matcher, reload_event, esp_log_bus)
```

- [ ] **Step 4: Factor `_trigger_auto_enroll` out of the old `_handle_checkin` unmatched-face branch**

The current code inserts a face_encoding row + signals reload_event when `pair.face_matched_user_id is None`. Lift that into a helper:

```python
def _trigger_auto_enroll(enroll, db, matcher, reload_event, esp_log_bus):
    user_name = db.get_user_name(enroll.grant_user_id)
    if user_name is None:
        return
    db.insert_face_encoding(enroll.grant_user_id, enroll.embedding.tobytes())
    reload_event.set()
    _audit(esp_log_bus, "info", "enroll",
           f"auto-enrolled face for user={user_name} via rfid")
```

- [ ] **Step 5: Update daemon init in `main()` / `SmartGateApp.__init__` to construct the new objects**

```python
# Remove:
# two_factor = TwoFactorState(ttl_s=4.0)

# Add:
from smart_gate.recognition.cooldown import UserCooldown
from smart_gate.recognition.auto_enroll_pair import AutoEnrollPairState

face_cooldown = UserCooldown(cfg.recognition.face_cooldown_s)
qr_cooldown = UserCooldown(cfg.recognition.qr_cooldown_s)
auto_enroll_state = AutoEnrollPairState(ttl_s=cfg.recognition.autoenroll_ttl_s)
```

Thread the three objects into the detector and the bus consumer / `_handle_esp_event` paths where the old `state` was passed.

- [ ] **Step 6: Tests pass + smoke import**

```bash
pytest tests/unit/ -v 2>&1 | tail -10
python -c "import smart_gate.main"
```

- [ ] **Step 7: Commit**

```bash
git add smart_gate/main.py tests/unit/test_main_bus.py
git commit -m "refactor(daemon): 1-of-3 channel routing in _handle_checkin + RFID handler

Each method writes one event row. cmd:open is sent only for face/qr —
RFID is already open via ESP shortcut. Auto-enroll factored out as
_trigger_auto_enroll, called from the RFID granted branch when
autoenroll_enabled is true.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 1.5.6: Delete legacy `two_factor.py` + its tests

**Files:**
- Delete: `smart_gate/recognition/two_factor.py`
- Delete: `tests/unit/test_two_factor.py`

- [ ] **Step 1: Confirm no remaining imports**

```bash
grep -rn 'two_factor\|TwoFactorState' smart_gate/ tests/
```

After Tasks 1.5.4 and 1.5.5, there should be zero hits in `smart_gate/`. The test file still imports — confirm and delete.

- [ ] **Step 2: Delete files**

```bash
git rm smart_gate/recognition/two_factor.py tests/unit/test_two_factor.py
```

- [ ] **Step 3: Full test suite must still pass**

```bash
pytest tests/unit/ -q 2>&1 | tail -5
```

- [ ] **Step 4: Commit**

```bash
git commit -m "chore(recognition): delete legacy two_factor module + tests

Superseded by cooldown.py + auto_enroll_pair.py. No remaining imports.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 1.5.7: Phase 1 + 1.5 combined verification gate (manual bench)

User-driven; same workflow as the parent plan's Task 1.11 with extended test matrix.

- [ ] **Step 1: Flash + restart**

Use the Task 1.11 flash workflow.

- [ ] **Step 2: Run the combined test matrix**

Parent plan Tests 1-9 (Phase 1) — see spec §10.3:

1. Quẹt thẻ không enrolled 5 lần → LCD restores
2. Deny then granted during buzzer → gate opens immediately
3. Missing config.toml → daemon warns + uses /dev/serial0
4. face_threshold = 0.25 in default toml
5. /events.json?range=today → UTC-correct
6. Hand 10 cm in front of HC-SR04 → obstacle icon
7. Card on RFID antenna → RFID icon
8. Swipe → i2c log line per swipe
9. 30 s idle → no lcd_write log lines

New Phase 1.5 tests — see spec §8:

10. Face alone → gate opens; event row method=face
11. QR alone → gate opens; event row method=qr
12. RFID alone → gate opens (ESP); event row method=rfid on Pi
13. 30 s standing → ≤ 6 face CheckInEvents per matched user (cooldown)
14. Tap card for un-faced user_002 + look at camera → auto-enroll; next face-alone visit opens
15. Show QR + unmatched face → opens via QR but NO face_encoding row inserted
16. Tap card while face already matches → no new encoding row
17. Legacy `consumption_cooldown_s` in /etc/smart-gate/config.toml → daemon starts cleanly, field ignored

- [ ] **Step 3: If all 17 pass → proceed to Phase 2 of parent plan. Else triage.**

- [ ] **Step 4: Update memory `smart_gate_auth_priority.md`**

The memory was written in advance of the code. After verification, edit it to add: "Code aligned with this decision on 2026-06-12 via spec/plan at docs/superpowers/specs/2026-06-12-smart-gate-auth-1-of-3-refactor-design.md."

---

## Summary

7 tasks, ~250 LOC net change, ~2 h impl + 30 min test.

| Task | LOC | Time | Risk |
|---|---|---|---|
| 1.5.1 cooldown | ~60 | 10 min | Low |
| 1.5.2 auto_enroll_pair | ~100 | 20 min | Low |
| 1.5.3 config + toml | ~14 | 10 min | Low |
| 1.5.4 detector refactor | ~80 | 30 min | Med (touches frame loop) |
| 1.5.5 main.py refactor | ~90 | 40 min | Med (touches _handle_checkin) |
| 1.5.6 delete legacy | ~150 deleted | 5 min | Low |
| 1.5.7 verify (manual) | — | 30 min | — |

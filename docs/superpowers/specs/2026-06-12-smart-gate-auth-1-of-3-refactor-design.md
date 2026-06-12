# Smart-gate auth refactor — 1-of-3 entry + auto-enroll on RFID grant

**Date**: 2026-06-12
**Author**: brainstorming session w/ Claude Code
**Status**: design approved, ready for implementation plan
**Related**: continues from [`2026-06-12-smart-gate-hang-and-robustness-fixes-design.md`](2026-06-12-smart-gate-hang-and-robustness-fixes-design.md). Inserts as **Phase 1.5** between P1 and P2 of that plan.

## 1. Background

User reviewed the current gate-open logic on 2026-06-12 and asked: "logic để hợp lệ vào cổng đang là gì, tôi muốn cả 3 phương pháp riêng lẻ đều có thể đi qua, 1 trong 3 thay vì 2 trong 3 như trước."

Investigation of the running code found the actual semantics are inconsistent across the two compute units:

| Channel | Gate opens? | Event row written? |
|---|---|---|
| Face match alone | ❌ no | ❌ |
| QR alone | ❌ no | ❌ |
| RFID alone (allowlisted) | ✅ ESP opens directly via its NVS allowlist | ❌ (Pi never sees a paired event) |
| Face + QR (within 4 s) | ✅ Pi sends `cmd:open` | ✅ |
| Face + RFID (within 4 s) | ✅ ESP opens, Pi later writes paired event | ✅ |

The driving module is `smart_gate/recognition/two_factor.py`. Its class `TwoFactorState` requires *both* a face slot and a credential slot to be fresh within `ttl_s` (default 4 s) before emitting a `CheckInPair`, which the daemon converts into a `CheckInEvent` and ultimately `cmd:open`. RFID is bolted on top: the ESP firmware reads its own NVS allowlist and acts independently, so a granted swipe physically opens the gate even when the Pi never sees a paired face.

The 2026-06-10 auth-priority decision (recorded in memory `smart_gate_auth_priority.md`) already specified 1-of-3 semantics. The code has not been refactored to match. This spec closes that gap.

## 2. Goals & non-goals

**Goals**
- Each of face, QR, and RFID independently opens the gate when its own criteria are met — without requiring a second factor.
- Every gate-open emits exactly one event row with `method ∈ {"face", "qr", "rfid"}`, `user_id`, and channel-specific detail. No silent opens.
- Auto-enroll continues to work, but only on the RFID → face pairing path (the existing UX where the user taps their card while looking at the camera so the system "learns" their face).
- Per-user cooldown prevents the detector from firing repeated CheckInEvents while the user stays in frame.
- Existing memory `smart_gate_auth_priority.md` (the 1-of-3 + threshold-0.25 facts) becomes accurate against the running code.

**Non-goals**
- Liveness detection for face. A printed photo can still pass.
- QR single-use tokens. A screenshot of a QR code remains valid until the operator deletes/regenerates the user.
- Multi-factor mandatory mode. The 1-of-3 model is the design.
- Refactoring the ESP allowlist path. RFID-grants continue to open via the ESP shortcut; the Pi only mirrors the event row.

## 3. Accepted residual risks

By choosing 1-of-3, the user accepts:
1. Stolen RFID card → entry.
2. Screenshot of QR → entry.
3. Face spoofing (photo / printed mask) → entry.

These were acknowledged during the 2026-06-10 brainstorming and reaffirmed during the 2026-06-12 review. Mitigation is procedural (revoke / rotate after compromise), not technical.

## 4. Success criteria

After the refactor ships:
- A face-match (distance < 0.25, matched user_id) with no card and no QR opens the gate.
- A valid QR with no face and no card opens the gate.
- A granted RFID swipe with no face and no QR opens the gate. (Behavior preserved; the Pi now also writes an event row.)
- Standing in front of the camera for 30 s produces at most ⌈30 / cooldown⌉ CheckInEvents per matched user (default cooldown = 5 s → ≤ 6 events).
- Swiping a granted card while showing your face within 4 s — and your face is currently unmatched in the encoding DB — auto-enrolls the face under the card's user_id. The next face-alone visit then opens the gate.
- Showing a QR with an unmatched face does NOT auto-enroll. (Regression test.)
- Existing `tests/unit/test_two_factor.py` semantics replaced with new tests for cooldowns + auto-enroll-on-RFID + 1-of-3 triggers; suite stays green.

## 5. Architecture

### 5.1 Decompose `TwoFactorState`

`TwoFactorState` does two jobs today: it gates gate-open, and it's the rendezvous slot for auto-enroll. These split.

- `smart_gate/recognition/auto_enroll_pair.py` — new module hosting `AutoEnrollPairState`. Same lock + slot structure as the old class but:
  - Only `source == "rfid"` grants enter the grant slot. QR / face writes are silently ignored.
  - The output type is renamed `EnrollCandidate` (face embedding + grant user_id + face distance) to make it obvious this is not a gate-open signal.
  - Drops `consumption_cooldown_s` — gate-open is no longer the trigger.

- `smart_gate/recognition/two_factor.py` — deleted. Imports updated. `TwoFactorState` was only used by `detector.py` and `main.py`.

### 5.2 New cooldown primitives

- `smart_gate/recognition/cooldown.py` — new module exposing `UserCooldown(window_s: float)` with two methods:
  - `passed(user_id: int) -> bool` — returns True if the user is not currently in cooldown (i.e., last `touch` was > `window_s` ago).
  - `touch(user_id: int) -> None` — records the moment the user just consumed.
  - Internal: `dict[int, float]` keyed by user_id, value = `time.monotonic()` of last touch. No size cap (smart-gate has tens of users, not millions).
- Two instances created at daemon start: `face_cooldown = UserCooldown(cfg.recognition.face_cooldown_s)` and `qr_cooldown = UserCooldown(cfg.recognition.qr_cooldown_s)`. Defaults 5 s each.

### 5.3 Channel paths

#### Face (camera detector)

Inside `detector.py` per frame, after the matcher returns `(matched_user_id, distance)`:

```python
if matched_user_id is not None and distance < cfg.recognition.face_threshold:
    if face_cooldown.passed(matched_user_id):
        face_cooldown.touch(matched_user_id)
        bus.put(CheckInEvent(method="face",
                             user_id=matched_user_id,
                             face_distance=distance))
# Always notify auto-enroll state — it only does anything if an RFID grant is pending.
auto_enroll_state.set_face_seen(embedding=embedding,
                                matched_user_id=matched_user_id,
                                distance=distance)
```

If `matched_user_id is None` (face seen but unrecognised): no gate-open, but `set_face_seen` still fires so an RFID-grant arriving within 4 s can pair it.

#### QR (camera detector)

Inside `detector.py` when a QR token decodes to `qr_user_id`:

```python
if qr_user_id is not None:
    if qr_cooldown.passed(qr_user_id):
        qr_cooldown.touch(qr_user_id)
        bus.put(CheckInEvent(method="qr",
                             user_id=qr_user_id))
```

No call into `auto_enroll_state` — QR never triggers enrollment.

#### RFID (Pi side, mirroring ESP)

`main.py` `evt:rfid` handler when `granted == true`:

```python
# Gate is already open (ESP shortcut). Mirror the event row + offer to auto-enroll.
bus.put(CheckInEvent(method="rfid", user_id=rfid_user_id, raw_uid=raw_uid))
if cfg.recognition.autoenroll_enabled:
    enroll = auto_enroll_state.set_grant_and_wait_for_face(rfid_user_id, "rfid")
    if enroll is not None:
        trigger_auto_enroll(enroll)   # existing path, reused
```

If `set_face_seen` arrives within `autoenroll_ttl_s = 4 s` with `matched_user_id is None`, the state returns an `EnrollCandidate` and the existing auto-enroll machinery (matcher.reload signal + DB insert of new encoding) runs.

### 5.4 `CheckInEvent` schema

Replace the old face-plus-grant dataclass with a per-channel one:

```python
@dataclass(frozen=True)
class CheckInEvent:
    method: str                    # "face" | "qr" | "rfid"
    user_id: int
    face_distance: float | None = None     # face only
    raw_uid: str | None = None             # rfid only
    qr_token: str | None = None            # qr only (for audit; not currently used)
```

The bus is the existing `queue.Queue` consumed by `_consume_bus` (P1 wrap intact).

### 5.5 `_handle_checkin` refactor

Single entry point in `main.py` (`_handle_checkin(evt, db, matcher, uart, trig_queue, cfg, last_grant)`):

1. Look up the user name via `db.get_user_name(evt.user_id)`. Unknown (the ESP allowlist holds a UID the Pi user table doesn't know about — possible if the operator added a UID via web UI then deleted the user but not the allowlist entry) → audit warn `_audit(esp_log_bus, "warn", evt.method, f"unknown user_id={evt.user_id}")` and return without writing an event row or sending `cmd:open`.
2. Insert an event row: `db.insert_event(method=evt.method, name=user_name, granted=True, detail=evt.face_distance_str_or_None)`.
3. If `evt.method != "rfid"` (face / QR), send `cmd:open` over UART. RFID is already open via the ESP shortcut; sending again would be a duplicate / ack-collide.
4. Audit a single line `_audit(esp_log_bus, "info", evt.method, f"open user={user_name}")`.

The current `_handle_checkin` is ~80 LOC of two-factor specific code. The rewrite is ~40 LOC of plain channel-routing.

### 5.6 Auto-enroll machinery

A new helper `trigger_auto_enroll(enroll: EnrollCandidate, db, matcher, reload_event, esp_log_bus)` factored out of the existing `_handle_checkin` body. The current code inserts the encoding row + fires `reload_event` inline inside `_handle_checkin` when the pair has `face_matched_user_id is None`; that logic moves into `trigger_auto_enroll` unchanged. The new helper:

1. Verifies `enroll.matched_user_id is None` (only enroll if the face is currently unrecognised — answers user's question 3).
2. Inserts a row into `face_encodings` with `(user_id=enroll.grant_user_id, embedding=enroll.embedding.tobytes())`.
3. Signals the matcher reload event (existing `reload_event` already wired up).
4. Audits `_audit(esp_log_bus, "info", "enroll", f"auto-enrolled face for user={user_name} via rfid")`.

If `enroll.matched_user_id` is not None — i.e. the face already matches *some* user, possibly a different one from the RFID grant — auto-enroll is skipped. This is the "face already enrolled, don't fight" rule confirmed during brainstorming.

### 5.7 Configuration

Add to `smart_gate/config.py` `RecognitionCfg`:

```python
@dataclass
class RecognitionCfg:
    # ... existing fields ...
    face_cooldown_s: float = 5.0      # new
    qr_cooldown_s: float = 5.0        # new
    autoenroll_ttl_s: float = 4.0     # new (was hardcoded ttl_s on TwoFactorState)
    autoenroll_enabled: bool = True   # new
```

And matching defaults in `packaging/config.default.toml`:

```toml
[recognition]
face_threshold = 0.25         # already in P1
face_cooldown_s = 5.0
qr_cooldown_s = 5.0
autoenroll_ttl_s = 4.0
autoenroll_enabled = true
```

The old `consumption_cooldown_s` field on TwoFactorState is removed; if it appears in an existing `/etc/smart-gate/config.toml`, the TOML loader silently ignores unknown fields (dataclasses' merge layer drops them with a debug log). No migration step required.

## 6. Files changed

```
smart_gate/recognition/two_factor.py        → DELETED
smart_gate/recognition/auto_enroll_pair.py  → NEW   (~40 LOC)
smart_gate/recognition/cooldown.py          → NEW   (~30 LOC)
smart_gate/recognition/detector.py          → ~30 LOC change (3 of: matched-face open, qr open, auto-enroll signal)
smart_gate/main.py                          → ~40 LOC change (_handle_checkin rewrite, rfid handler, init wiring)
smart_gate/config.py                        → +4 LOC (new RecognitionCfg fields)
packaging/config.default.toml               → +4 LOC
tests/unit/test_two_factor.py               → DELETED
tests/unit/test_auto_enroll_pair.py         → NEW   (~70 LOC, slot + ttl + RFID-only filter tests)
tests/unit/test_cooldown.py                 → NEW   (~30 LOC, passed/touch behavior)
tests/unit/test_main_bus.py                 → +50 LOC (1-of-3 trigger tests + auto-enroll regression)
tests/unit/test_config.py                   → +6 LOC (new field defaults)
```

**LOC total**: ~250 net additions across new files + edits, against ~150 LOC removed (old `two_factor.py` + its test file). **Impl time**: ~2 h. **Test time**: ~30 min.

## 7. Sequencing inside the existing plan

This phase inserts between Phase 1 and Phase 2 of the parent plan, ordered as Phase 1.5. Rationale:

- P1 fixes the user-reported LCD hang and ships safety quick-wins. Verifying it on the bench is still valuable in isolation.
- P1.5 reshapes Pi-side recognition logic. It touches no firmware — flashing happens once at end of P1 to verify the LCD hang fix, then again after P1.5 (or at end of P2 if no new firmware accumulates). Per user's request 2026-06-12 ("Pause P1 verify, làm auth refactor trước rồi flash 1 lần cho cả hai"), the flash is deferred and both phases verified together.
- P2 (input hardening) is downstream of P1.5 because some of its DB-transaction work touches `_handle_checkin`. Doing P1.5 first keeps the transaction wrap aligned with the new shape of `_handle_checkin`.

## 8. Verification (manual, end of P1 + P1.5 combined)

The original P1 verification matrix (spec §10.3) runs first. Then the P1.5 additions:

1. **Face alone**: enrolled user stands in front of camera; no card, no QR shown. Within ~1 s the gate opens. Dashboard event row `method=face user=user_001 detail=face_distance=0.18` (or similar).
2. **QR alone**: pull QR from `/qr/<name>.png` on phone, show to camera, no face match (cover face). Gate opens. Event row `method=qr user=user_001`.
3. **RFID alone**: tap card, do not look at camera. Gate opens (ESP path). Event row `method=rfid user=user_001 raw_uid=A1B2C3D4`.
4. **Face cooldown**: enrolled user stays in frame 30 s. Bus consumer's event count for that user ≤ 6 over the window (5 s cooldown).
5. **Auto-enroll on RFID**: enroll user_002 in DB without a face (admin enrolls via web). Tap user_002's card, then look at camera within 4 s. After ~1 s the matcher reloads. Standing in front of camera again 6 s later → gate opens via face alone.
6. **No auto-enroll on QR**: enroll user_003 with no face. Show user_003's QR + look at camera. Gate opens via QR (event row method=qr). DB row count for `face_encodings WHERE user_id=user_003` stays 0.
7. **No auto-enroll when face already matches**: tap user_001's card while user_001's face is in frame (already enrolled). No new encoding row inserted.
8. **Legacy config compat**: paste `consumption_cooldown_s = 7.0` into `/etc/smart-gate/config.toml`. Restart daemon. Daemon starts cleanly; the field is ignored; no crash.

## 9. Risk & rollback

| Risk | Detection | Rollback |
|---|---|---|
| `_handle_checkin` rewrite breaks an existing event path | `pytest tests/unit/test_main_bus.py` red, or P1.5 verify test 1-3 fails | `git revert` the P1.5 commit batch on `feat/safety-fixes`; original `two_factor.py` restored from git history |
| Cooldown too short → spam events still | P1.5 verify test 4 fails | bump `face_cooldown_s` in config; no code change |
| Auto-enroll fires on QR (regression) | P1.5 verify test 6 produces an encoding row | The `set_grant_and_wait_for_face` filter is one line; bug fix is targeted |
| Existing `/etc/smart-gate/config.toml` with no new fields | Default merge kicks in; no behavior change at first glance — but the new face-alone path activates immediately, which may surprise the operator | Document in commit message: "After upgrading, face-alone opens are enabled by default. Set `[recognition].autoenroll_enabled = false` in config if you want to disable face auto-enroll." |

## 10. Out of scope / accepted residual risks (recap)

- No liveness detection. Face spoof via photo remains possible.
- No QR single-use enforcement. Screenshot reuse remains possible.
- No anti-tailgating logic. One open per credential per cooldown window.
- No multi-factor *option*. The model is strictly 1-of-3; an operator who wants 2FA must add it later as a config option.

## 11. Implementation tactic

- One commit per logical step (parallels P1 cadence): cooldown module, auto_enroll_pair module, detector refactor, main.py refactor, config + defaults, tests. ~6 commits.
- Each commit is independently revertable.
- No flash required for P1.5 (Pi-only). Verify gate combines with P1's flash test.
- Memory `smart_gate_auth_priority.md` updated *after* the verify gate passes, not before — keep it accurate against running code.

"""Detector thread: per-frame face encode + QR decode -> CheckInEvent on bus.

Face detection backends (priority order):
1. MediaPipe (`mp.solutions.face_detection.FaceDetection`) — fastest (~1 ms/frame
   on Pi 4) but not available on Python 3.13 yet (no upstream wheel).
2. face_recognition's HOG via `face_recognition.face_locations(model="hog")` —
   ~100 ms/frame on Pi 4, pure dlib, available everywhere face_recognition is.

If MediaPipe import fails at default-deps time, the HOG backend is used. Tests
inject `deps` directly and can supply either backend.
"""
from __future__ import annotations

import dataclasses
import logging
import threading
import time

from smart_gate.recognition.auto_enroll_pair import AutoEnrollPairState
from smart_gate.recognition.cooldown import UserCooldown

log = logging.getLogger(__name__)


@dataclasses.dataclass
class AuthEvent:
    """Legacy 1-factor event. Kept for manual_open/close from the web only.
    Detector no longer emits AuthEvent for face or QR; it emits CheckInEvent
    when face+grant are both present.
    """
    method: str                     # 'manual_open' | 'manual_close'
    user_id: int | None
    granted: bool
    detail: dict = dataclasses.field(default_factory=dict)
    ts_mono: float = dataclasses.field(default_factory=time.monotonic)


@dataclasses.dataclass(frozen=True)
class CheckInEvent:
    """1-of-3 check-in event. Each auth channel (face / qr / rfid) fires its
    own CheckInEvent independently; per-user cooldowns prevent repeated
    firing while the same user stays in frame / keeps the card on the reader.
    """
    method: str                            # 'face' | 'qr' | 'rfid'
    user_id: int
    face_distance: float | None = None     # face only
    raw_uid: str | None = None             # rfid only
    qr_token: str | None = None            # qr only
    ts_mono: float = dataclasses.field(default_factory=time.monotonic)


class _UncertainCounter:
    """Tracks consecutive frames where a borderline (uncertain-band) match
    keeps pointing at the same user_id. Resets the moment the user_id
    changes, no match is reported, or a strict (sub-threshold) match
    arrives. See the 3-tier face decision in `_process_frame`.
    """
    def __init__(self) -> None:
        self._last_uid: int | None = None
        self._count: int = 0

    def touch(self, uid: int) -> None:
        if uid != self._last_uid:
            self._last_uid = uid
            self._count = 1
        else:
            self._count += 1

    def count(self, uid: int) -> int:
        return self._count if uid == self._last_uid else 0

    def clear(self) -> None:
        self._last_uid = None
        self._count = 0


_uncertain_counter = _UncertainCounter()


def run_detector(cfg, hub, matcher, event_bus, shutdown: threading.Event,
                 *, deps=None, overlay=None,
                 face_cooldown: UserCooldown | None = None,
                 qr_cooldown: UserCooldown | None = None,
                 auto_enroll_state: AutoEnrollPairState | None = None,
                 fps_counter=None) -> None:
    """Detector loop. `deps` is an optional dict for test injection:
        {"cv2":..., "mp_face":<obj|None>, "face_recognition":..., "pyzbar":...}
    When `mp_face` is None (or absent), HOG via `face_recognition.face_locations`
    is used instead.

    `face_cooldown` and `qr_cooldown` are `UserCooldown` instances that
    suppress duplicate CheckInEvents for the same user within a window.
    `auto_enroll_state` is an `AutoEnrollPairState`; the detector pokes it
    on every face frame so RFID-triggered auto-enroll can latch.
    """
    if deps is None:
        import cv2 as _cv2
        import face_recognition as _fr
        from pyzbar import pyzbar as _pz
        mp_face = None
        try:
            import mediapipe as _mp
            mp_face = _mp.solutions.face_detection.FaceDetection(
                model_selection=0,
                min_detection_confidence=cfg.recognition.mediapipe_min_conf,
            )
            log.info("face detector backend: mediapipe")
        except Exception as e:
            log.info("mediapipe unavailable (%s); falling back to HOG", e)
        deps = {
            "cv2": _cv2,
            "mp_face": mp_face,
            "face_recognition": _fr,
            "pyzbar": _pz,
        }

    # Rate-limit per-frame exception logging. A malformed encoding in the
    # matcher can raise on every frame (~20 Hz) and blow ~50 MB/min into
    # app.log via log.exception's traceback. If errors exceed 5/s, emit a
    # single warning and sleep 500 ms to throttle.
    err_window_start = time.monotonic()
    err_count = 0

    while not shutdown.is_set():
        bgr = hub.wait_bgr(timeout=1.0)
        if bgr is None:
            continue
        try:
            _process_frame(bgr, cfg, matcher, event_bus, deps,
                           overlay=overlay,
                           face_cooldown=face_cooldown,
                           qr_cooldown=qr_cooldown,
                           auto_enroll_state=auto_enroll_state)
            if fps_counter is not None:
                fps_counter.tick()
        except Exception as e:
            log.exception("detector frame failed: %s", e)
            now = time.monotonic()
            if now - err_window_start > 1.0:
                err_window_start = now
                err_count = 0
            err_count += 1
            if err_count > 5:
                log.warning("detector: errors >5/s, sleeping 0.5s")
                time.sleep(0.5)
                err_count = 0   # reset after the sleep


def _process_frame(bgr, cfg, matcher, bus, deps, *, overlay=None,
                   face_cooldown=None, qr_cooldown=None,
                   auto_enroll_state=None):
    cv2 = deps["cv2"]
    pyzbar = deps["pyzbar"]
    fr = deps["face_recognition"]
    mp_face = deps.get("mp_face")

    # --- Face first ---
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    if mp_face is not None:
        bbox, encs = _detect_and_encode_mediapipe(rgb, mp_face, fr)
    else:
        bbox, encs = _detect_and_encode_hog(rgb, fr)

    if not encs:
        if overlay is not None:
            overlay.clear()
    else:
        probe = encs[0].astype("float32")
        user_id, distance = matcher.match_face(probe)
        is_match = (user_id is not None
                    and distance < cfg.recognition.face_threshold)
        # Overlay: green if matched, red if not. Display only, no DB write.
        if overlay is not None:
            if is_match:
                name = (matcher.user_name(user_id)
                        if hasattr(matcher, "user_name") else f"id={user_id}")
                overlay.set(bbox, f"{name} ({distance:.2f})",
                            color=(0, 255, 0))
            else:
                lbl = (f"unknown ({distance:.2f})"
                       if distance != float("inf") else "unknown")
                overlay.set(bbox, lbl, color=(0, 0, 255))

        # 1-of-3 face channel: 3-tier decision (decided 2026-06-13).
        #   strict   (distance < face_threshold)              → fire now
        #   borderline (face_threshold <= distance <= band_hi) → fire only
        #     after N consecutive frames matching the same user_id
        #   reject   (distance > band_hi or no candidate)      → clear band
        # All fires are still gated by `face_cooldown` (per-user).
        matched_user_id = user_id if is_match else None
        band_lo, band_hi = cfg.recognition.uncertain_band
        required_consec = cfg.recognition.uncertain_required_consecutive

        if (matched_user_id is not None
                and distance < cfg.recognition.face_threshold):
            # Strict accept — short-circuit, reset borderline tracker.
            _uncertain_counter.clear()
            if face_cooldown is None or face_cooldown.passed(matched_user_id):
                if face_cooldown is not None:
                    face_cooldown.touch(matched_user_id)
                bus.put(CheckInEvent(
                    method="face",
                    user_id=matched_user_id,
                    face_distance=float(distance),
                ))
        elif (user_id is not None
                and band_lo <= distance <= band_hi):
            # Borderline — accumulate consecutive frames for the same user.
            _uncertain_counter.touch(user_id)
            if _uncertain_counter.count(user_id) >= required_consec:
                _uncertain_counter.clear()
                if face_cooldown is None or face_cooldown.passed(user_id):
                    if face_cooldown is not None:
                        face_cooldown.touch(user_id)
                    bus.put(CheckInEvent(
                        method="face",
                        user_id=user_id,
                        face_distance=float(distance),
                    ))
        else:
            # No candidate, or distance > band_hi — explicit reject.
            _uncertain_counter.clear()

        # Auto-enroll signal — fires only if a fresh RFID grant is pending.
        if auto_enroll_state is not None:
            auto_enroll_state.set_face_seen(
                embedding=probe,
                matched_user_id=matched_user_id,
                distance=(float(distance)
                          if distance != float("inf") else 1e9),
            )

    # --- QR ---
    for sym in pyzbar.decode(bgr):
        try:
            token = sym.data.decode("utf-8", errors="replace")
        except Exception:
            continue
        qr_user_id = matcher.lookup_qr(token)
        if qr_user_id is None:
            continue
        if qr_user_id is not None:
            if qr_cooldown is None or qr_cooldown.passed(qr_user_id):
                if qr_cooldown is not None:
                    qr_cooldown.touch(qr_user_id)
                bus.put(CheckInEvent(
                    method="qr",
                    user_id=qr_user_id,
                    qr_token=token,
                ))
        # Intentionally no auto-enroll call for QR.
        # Only first valid QR per frame counts.
        break


def _detect_and_encode_mediapipe(rgb, mp_face, fr):
    """Returns (bbox, encodings). bbox is (x, y, w, h) pixel coords or None."""
    result = mp_face.process(rgb)
    if not getattr(result, "detections", None):
        return None, []
    box = _best_box(result.detections, rgb.shape)
    if box is None:
        return None, []
    roi = _pad_and_crop(rgb, box, pad=0.20)
    encs = fr.face_encodings(roi, num_jitters=1)
    return box, encs


def _detect_and_encode_hog(rgb, fr):
    locations = fr.face_locations(rgb, model="hog",
                                  number_of_times_to_upsample=1)
    if not locations:
        return None, []
    # Keep the largest face only.
    locations.sort(key=lambda l: (l[2] - l[0]) * (l[1] - l[3]), reverse=True)
    encs = fr.face_encodings(rgb, known_face_locations=locations[:1],
                             num_jitters=1)
    top, right, bottom, left = locations[0]
    bbox = (left, top, right - left, bottom - top)
    return bbox, encs


def _best_box(detections, rgb_shape):
    h, w = rgb_shape[:2]
    best = None
    best_score = -1.0
    for det in detections:
        score = float(det.score[0]) if det.score else 0.0
        if score > best_score:
            best_score = score
            rb = det.location_data.relative_bounding_box
            x = max(0, int(rb.xmin * w))
            y = max(0, int(rb.ymin * h))
            bw = max(1, int(rb.width * w))
            bh = max(1, int(rb.height * h))
            best = (x, y, bw, bh)
    return best


def _pad_and_crop(rgb, box, pad: float):
    h, w = rgb.shape[:2]
    x, y, bw, bh = box
    px = int(bw * pad)
    py = int(bh * pad)
    x0 = max(0, x - px)
    y0 = max(0, y - py)
    x1 = min(w, x + bw + px)
    y1 = min(h, y + bh + py)
    return rgb[y0:y1, x0:x1]

"""Detector thread: per-frame face encode + QR decode -> AuthEvent on bus.

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

import numpy as np

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


@dataclasses.dataclass
class CheckInEvent:
    """Two-factor check-in: detector saw a face AND a credential within TTL.
    The bus consumer turns this into a DB event row and a cmd:open."""
    face_matched_user_id: int | None       # None ⇒ auto-enroll embedding under grant_user_id
    face_embedding: bytes | None           # for auto-enroll; numpy serialised
    face_distance: float
    grant_user_id: int
    grant_source: str                      # 'qr' or 'rfid'
    ts_mono: float = dataclasses.field(default_factory=time.monotonic)


def run_detector(cfg, hub, matcher, event_bus, shutdown: threading.Event,
                 *, deps=None, overlay=None, state=None,
                 fps_counter=None) -> None:
    """Detector loop. `deps` is an optional dict for test injection:
        {"cv2":..., "mp_face":<obj|None>, "face_recognition":..., "pyzbar":...}
    When `mp_face` is None (or absent), HOG via `face_recognition.face_locations`
    is used instead.
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

    while not shutdown.is_set():
        bgr = hub.wait_bgr(timeout=1.0)
        if bgr is None:
            continue
        try:
            _process_frame(bgr, cfg, matcher, event_bus, deps, overlay, state)
            if fps_counter is not None:
                fps_counter.tick()
        except Exception as e:
            log.exception("detector frame failed: %s", e)


def _process_frame(bgr, cfg, matcher, bus, deps, overlay=None, state=None):
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

    pair_from_face = None
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
        # Update two-factor state with this face. If a credential grant was
        # already pending in TTL, we'll get a CheckInPair back.
        if state is not None:
            pair_from_face = state.set_face_and_try_match(
                embedding=probe,
                matched_user_id=user_id if is_match else None,
                distance=float(distance) if distance != float("inf") else 1e9,
            )

    # --- QR ---
    pair_from_qr = None
    for sym in pyzbar.decode(bgr):
        try:
            token = sym.data.decode("utf-8", errors="replace")
        except Exception:
            continue
        qr_user_id = matcher.lookup_qr(token)
        if qr_user_id is None:
            continue
        if state is not None:
            pair_from_qr = state.set_grant_and_try_match(qr_user_id, "qr")
        # Only first valid QR per frame counts
        break

    # Emit at most one CheckInEvent per frame.
    pair = pair_from_face or pair_from_qr
    if pair is not None:
        bus.put(CheckInEvent(
            face_matched_user_id=pair.face_matched_user_id,
            face_embedding=(pair.face_embedding.astype("float32").tobytes()
                            if pair.face_matched_user_id is None else None),
            face_distance=pair.face_distance,
            grant_user_id=pair.grant_user_id,
            grant_source=pair.grant_source,
        ))


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

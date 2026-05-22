"""Detector thread: per-frame face encode + QR decode -> AuthEvent on bus."""
from __future__ import annotations

import dataclasses
import logging
import threading
import time

log = logging.getLogger(__name__)


@dataclasses.dataclass
class AuthEvent:
    method: str                     # 'face' | 'qr'
    user_id: int | None
    granted: bool
    detail: dict = dataclasses.field(default_factory=dict)
    ts_mono: float = dataclasses.field(default_factory=time.monotonic)


def run_detector(cfg, hub, matcher, event_bus, shutdown: threading.Event,
                 *, deps=None) -> None:
    """Detector loop. `deps` is an optional dict for test injection:
        {"cv2":..., "mp_face":..., "face_recognition":..., "pyzbar":...}
    """
    if deps is None:
        import cv2 as _cv2
        import mediapipe as _mp
        import face_recognition as _fr
        from pyzbar import pyzbar as _pz
        deps = {
            "cv2": _cv2,
            "mp_face": _mp.solutions.face_detection.FaceDetection(
                model_selection=0,
                min_detection_confidence=cfg.recognition.mediapipe_min_conf,
            ),
            "face_recognition": _fr,
            "pyzbar": _pz,
        }

    while not shutdown.is_set():
        bgr = hub.wait_bgr(timeout=1.0)
        if bgr is None:
            continue
        try:
            _process_frame(bgr, cfg, matcher, event_bus, deps)
        except Exception as e:
            log.exception("detector frame failed: %s", e)


def _process_frame(bgr, cfg, matcher, bus, deps):
    cv2 = deps["cv2"]
    pyzbar = deps["pyzbar"]
    fr = deps["face_recognition"]
    mp_face = deps["mp_face"]

    # --- QR
    for sym in pyzbar.decode(bgr):
        try:
            token = sym.data.decode("utf-8", errors="replace")
        except Exception:
            continue
        user_id = matcher.lookup_qr(token)
        if user_id is not None:
            bus.put(AuthEvent("qr", user_id, granted=True))

    # --- Face
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    result = mp_face.process(rgb)
    if not getattr(result, "detections", None):
        return
    box = _best_box(result.detections, rgb.shape)
    if box is None:
        return
    roi = _pad_and_crop(rgb, box, pad=0.20)
    encs = fr.face_encodings(roi, num_jitters=1)
    if not encs:
        return
    import numpy as np
    probe = encs[0].astype("float32")
    user_id, distance = matcher.match_face(probe)
    if user_id is not None and distance < cfg.recognition.face_threshold:
        bus.put(AuthEvent("face", user_id, granted=True,
                          detail={"distance": float(distance)}))
    elif distance > cfg.recognition.uncertain_band[1]:
        bus.put(AuthEvent("face", None, granted=False,
                          detail={"distance": float(distance)}))


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

"""Camera capture thread.

Wraps cv2.VideoCapture(V4L2, MJPG) and publishes every frame to FrameHub
+ recorder RingBuffer.
"""
from __future__ import annotations

import logging
import threading
import time

log = logging.getLogger(__name__)


def run_capture(cfg, hub, ring, shutdown: threading.Event,
                cv2_module=None) -> None:
    """Top-level entry. cv2_module is injectable for tests."""
    if cv2_module is None:
        import cv2 as cv2_module                   # imported lazily

    cap = _open_camera(cv2_module, cfg)
    fail_streak = 0
    while not shutdown.is_set():
        ok, frame = cap.read()
        if not ok:
            fail_streak += 1
            if fail_streak >= 30:
                log.error("camera read failed 30x — reopening")
                cap.release()
                time.sleep(0.5)
                cap = _open_camera(cv2_module, cfg)
                fail_streak = 0
            continue
        fail_streak = 0
        ok2, jpg = cv2_module.imencode(".jpg", frame,
                                       [cv2_module.IMWRITE_JPEG_QUALITY, 75])
        if not ok2:
            continue
        jpg_bytes = jpg.tobytes()
        hub.publish(jpg_bytes, frame)
        if ring is not None:
            ring.push(jpg_bytes, time.monotonic())
    hub.publish(None, None)
    cap.release()


def _open_camera(cv2_module, cfg):
    while True:
        cap = cv2_module.VideoCapture(cfg.video.camera_index, cv2_module.CAP_V4L2)
        if cap.isOpened():
            cap.set(cv2_module.CAP_PROP_FOURCC,
                    cv2_module.VideoWriter_fourcc(*"MJPG"))
            cap.set(cv2_module.CAP_PROP_FRAME_WIDTH, cfg.video.width)
            cap.set(cv2_module.CAP_PROP_FRAME_HEIGHT, cfg.video.height)
            cap.set(cv2_module.CAP_PROP_FPS, cfg.video.fps)
            cap.set(cv2_module.CAP_PROP_BUFFERSIZE, 1)
            log.info("camera %d open @ %dx%d %dfps",
                     cfg.video.camera_index, cfg.video.width,
                     cfg.video.height, cfg.video.fps)
            return cap
        log.warning("camera not available, retry in 5s")
        time.sleep(5)

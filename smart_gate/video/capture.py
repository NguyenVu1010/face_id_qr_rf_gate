"""Camera capture thread.

Wraps cv2.VideoCapture(V4L2, MJPG) and publishes every frame to FrameHub
+ recorder RingBuffer.

The capture loop keeps trying when the camera is absent: it logs a single
WARNING on first failure, then a status line at most once per 60 s after
that. When the camera reappears the cap thread logs a single INFO line
and resumes publishing frames. The daemon never exits because of a
missing camera.
"""
from __future__ import annotations

import logging
import os
import threading
import time

log = logging.getLogger(__name__)

# Suppress OpenCV's native stderr warnings ("[ WARN:0@... ] global cap_v4l.cpp")
# which would otherwise spam stderr every 5 s while the camera is absent.
# Must be set before cv2 is imported the first time.
os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")

_LOG_THROTTLE_S = 60.0


def run_capture(cfg, hub, ring, shutdown: threading.Event,
                cv2_module=None) -> None:
    """Top-level entry. cv2_module is injectable for tests."""
    if cv2_module is None:
        import cv2 as cv2_module                   # imported lazily

    cap = _open_camera(cv2_module, cfg, shutdown)
    if cap is None:
        hub.publish(None, None)
        return
    fail_streak = 0
    while not shutdown.is_set():
        ok, frame = cap.read()
        if not ok:
            fail_streak += 1
            if fail_streak >= 30:
                log.error("camera read failed 30x — reopening")
                cap.release()
                if shutdown.wait(0.5):
                    break
                cap = _open_camera(cv2_module, cfg, shutdown)
                if cap is None:
                    break
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
    if cap is not None:
        cap.release()


def _open_camera(cv2_module, cfg, shutdown: threading.Event | None = None):
    fail_count = 0
    last_log_mono = 0.0
    while shutdown is None or not shutdown.is_set():
        cap = cv2_module.VideoCapture(cfg.video.camera_index, cv2_module.CAP_V4L2)
        if cap.isOpened():
            cap.set(cv2_module.CAP_PROP_FOURCC,
                    cv2_module.VideoWriter_fourcc(*"MJPG"))
            cap.set(cv2_module.CAP_PROP_FRAME_WIDTH, cfg.video.width)
            cap.set(cv2_module.CAP_PROP_FRAME_HEIGHT, cfg.video.height)
            cap.set(cv2_module.CAP_PROP_FPS, cfg.video.fps)
            cap.set(cv2_module.CAP_PROP_BUFFERSIZE, 1)
            if fail_count > 0:
                log.info("camera %d recovered after %d retries; open @ %dx%d %dfps",
                         cfg.video.camera_index, fail_count, cfg.video.width,
                         cfg.video.height, cfg.video.fps)
            else:
                log.info("camera %d open @ %dx%d %dfps",
                         cfg.video.camera_index, cfg.video.width,
                         cfg.video.height, cfg.video.fps)
            return cap
        now = time.monotonic()
        if fail_count == 0:
            log.warning("camera %d not available; will keep retrying every 5s "
                        "(further messages throttled to once per minute)",
                        cfg.video.camera_index)
            last_log_mono = now
        elif now - last_log_mono >= _LOG_THROTTLE_S:
            log.warning("camera %d still not available (attempt %d)",
                        cfg.video.camera_index, fail_count + 1)
            last_log_mono = now
        fail_count += 1
        if shutdown is None:
            time.sleep(5)
        elif shutdown.wait(5.0):
            return None
    return None

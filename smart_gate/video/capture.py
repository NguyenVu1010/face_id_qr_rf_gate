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

# How long an identical JPEG stream can persist before we suspect the
# camera has hung and force a reopen. ~5s = comfortably longer than the
# longest legitimate freeze (lighting change auto-exposure rebake) but
# short enough that the demo recovers in time for the next visitor.
_STALE_FRAME_WINDOW_S = 5.0


def run_capture(cfg, hub, ring, shutdown: threading.Event,
                cv2_module=None) -> None:
    """Top-level entry. cv2_module is injectable for tests.

    Reopens the camera on TWO failure modes:
      a) cap.read() returns ok=False 30 times in a row (classic V4L2 fail).
      b) cap.read() returns ok=True but the JPEG bytes haven't changed in
         the last `_STALE_FRAME_WINDOW_S` seconds — covers cheap UVC chips
         (Jieli, some CH9329 carrier boards) that freeze the device while
         cv2 keeps returning a cached frame from the kernel buffer.
    """
    if cv2_module is None:
        import cv2 as cv2_module

    cap = _open_camera(cv2_module, cfg, shutdown)
    if cap is None:
        hub.publish(None, None)
        return
    fail_streak = 0
    last_unique_mono = time.monotonic()
    last_jpeg_hash: int | None = None
    while not shutdown.is_set():
        ok, frame = cap.read()
        if not ok:
            fail_streak += 1
            if fail_streak >= 30:
                log.error("camera read failed 30x — reopening")
                cap = _reopen(cap, cv2_module, cfg, shutdown)
                if cap is None:
                    break
                fail_streak = 0
                last_unique_mono = time.monotonic()
                last_jpeg_hash = None
            continue
        fail_streak = 0
        ok2, jpg = cv2_module.imencode(".jpg", frame,
                                       [cv2_module.IMWRITE_JPEG_QUALITY, 75])
        if not ok2:
            continue
        jpg_bytes = jpg.tobytes()
        # Stale-frame watchdog: compare cheap hash of JPEG. If unchanged
        # for too long, the camera is hung even though cv2 says ok.
        jpg_hash = hash(jpg_bytes[:1024])      # 1 KB suffices to distinguish
        now = time.monotonic()
        if jpg_hash != last_jpeg_hash:
            last_jpeg_hash = jpg_hash
            last_unique_mono = now
        elif now - last_unique_mono > _STALE_FRAME_WINDOW_S:
            log.error("camera frames stale for %.1fs (cv2 returns cached) — "
                      "reopening", now - last_unique_mono)
            cap = _reopen(cap, cv2_module, cfg, shutdown)
            if cap is None:
                break
            last_unique_mono = time.monotonic()
            last_jpeg_hash = None
            continue
        hub.publish(jpg_bytes, frame)
        if ring is not None:
            ring.push(jpg_bytes, now)
    hub.publish(None, None)
    if cap is not None:
        cap.release()


def _reopen(cap, cv2_module, cfg, shutdown):
    """Release the current cap handle and reopen, sleeping briefly so the
    USB stack can settle. Returns the new cap or None on shutdown."""
    try:
        cap.release()
    except Exception:
        pass
    if shutdown.wait(1.0):
        return None
    return _open_camera(cv2_module, cfg, shutdown)


def _camera_source(cfg):
    """Return the cv2.VideoCapture source: device path string if camera_device
    is set, otherwise the integer camera_index."""
    if cfg.video.camera_device:
        return cfg.video.camera_device
    return cfg.video.camera_index


def _open_camera(cv2_module, cfg, shutdown: threading.Event | None = None):
    fail_count = 0
    last_log_mono = 0.0
    source = _camera_source(cfg)
    while shutdown is None or not shutdown.is_set():
        cap = cv2_module.VideoCapture(source, cv2_module.CAP_V4L2)
        if cap.isOpened():
            cap.set(cv2_module.CAP_PROP_FOURCC,
                    cv2_module.VideoWriter_fourcc(*"MJPG"))
            cap.set(cv2_module.CAP_PROP_FRAME_WIDTH, cfg.video.width)
            cap.set(cv2_module.CAP_PROP_FRAME_HEIGHT, cfg.video.height)
            cap.set(cv2_module.CAP_PROP_FPS, cfg.video.fps)
            cap.set(cv2_module.CAP_PROP_BUFFERSIZE, 1)
            if fail_count > 0:
                log.info("camera %s recovered after %d retries; open @ %dx%d %dfps",
                         source, fail_count, cfg.video.width,
                         cfg.video.height, cfg.video.fps)
            else:
                log.info("camera %s open @ %dx%d %dfps",
                         source, cfg.video.width,
                         cfg.video.height, cfg.video.fps)
            return cap
        now = time.monotonic()
        if fail_count == 0:
            log.warning("camera %s not available; will keep retrying every 5s "
                        "(further messages throttled to once per minute)",
                        source)
            last_log_mono = now
        elif now - last_log_mono >= _LOG_THROTTLE_S:
            log.warning("camera %s still not available (attempt %d)",
                        source, fail_count + 1)
            last_log_mono = now
        fail_count += 1
        if shutdown is None:
            time.sleep(5)
        elif shutdown.wait(5.0):
            return None
    return None

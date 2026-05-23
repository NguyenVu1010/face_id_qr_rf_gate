"""Enrollment: capture N face samples + insert encodings + signal daemon.

Two capture modes:
- Interactive (default): cv2.imshow window with face bbox preview; press SPACE
  to capture each sample. Requires X / Wayland session.
- Headless (--headless): no GUI. Sleeps `--delay-s` seconds between captures,
  saving the first frame that has a detectable face. Suitable for SSH-only
  setups; just position your face in front of the webcam during the run.

Detector backend: tries MediaPipe first, falls back to face_recognition's
HOG (same logic as the daemon's run-time detector). On Python 3.13 where
MediaPipe has no wheel, the HOG path is used automatically.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
import numpy as np

from smart_gate.cli._signal import signal_daemon
from smart_gate.cli import qr as qr_mod

log = logging.getLogger(__name__)


def enroll(db, name: str, qr_dir: Path, n_samples: int = 5,
           camera_index=0, *, headless: bool = False,
           delay_s: float = 1.0, deps=None) -> Path:
    """Returns the path of the generated QR PNG.

    Args:
        db: Database instance
        name: user name (must be unique)
        qr_dir: directory for QR PNG output
        n_samples: number of face samples to capture
        camera_index: int index or string path (e.g. /dev/smart-gate-camera)
        headless: if True, skip cv2.imshow / waitKey; auto-capture instead
        delay_s: seconds to wait between samples in headless mode
        deps: optional dict for test injection
    """
    if deps is None:
        deps = _default_deps()
    if db.get_user_id_by_name(name) is not None:
        raise SystemExit(f"user already exists: {name}")
    uid = db.insert_user(name)

    try:
        if headless:
            encs = _capture_samples_headless(name, n_samples, camera_index,
                                             delay_s, deps)
        else:
            encs = _capture_samples_interactive(name, n_samples, camera_index,
                                                deps)
    except Exception:
        db.delete_user(name)
        raise

    if len(encs) < n_samples:
        db.delete_user(name)
        raise SystemExit(f"only captured {len(encs)}/{n_samples} samples; aborted")
    for i, enc in enumerate(encs):
        db.insert_face_encoding(uid, enc.astype("float32").tobytes(), i)

    path = qr_mod.issue_initial(db, name, qr_dir)
    signal_daemon()
    print(f"enrolled {name} ({len(encs)} samples). QR: {path}")
    return path


def _default_deps():
    import cv2 as _cv2
    import face_recognition as _fr
    mp_face = None
    try:
        import mediapipe as _mp
        mp_face = _mp.solutions.face_detection.FaceDetection(
            model_selection=0, min_detection_confidence=0.7)
    except Exception as e:
        log.info("mediapipe unavailable (%s); using HOG", e)
    return {
        "cv2": _cv2,
        "mp_face": mp_face,
        "face_recognition": _fr,
    }


def _capture_samples_interactive(name, n_samples, camera_index, deps):
    cv2 = deps["cv2"]
    mp_face = deps.get("mp_face")
    fr = deps["face_recognition"]
    cap = cv2.VideoCapture(camera_index, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    win = f"enroll: {name}"
    cv2.namedWindow(win)
    encs = []
    print("Press SPACE to capture a sample, ESC to abort.")
    try:
        while len(encs) < n_samples:
            ok, frame = cap.read()
            if not ok:
                continue
            annotated = frame.copy()
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            box = _find_face_box(rgb, mp_face, fr)
            if box is not None:
                x, y, bw, bh = box
                cv2.rectangle(annotated, (x, y), (x + bw, y + bh),
                              (0, 255, 0), 2)
            cv2.putText(annotated, f"{len(encs)}/{n_samples}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
            cv2.imshow(win, annotated)
            k = cv2.waitKey(30) & 0xFF
            if k == 27:                     # ESC
                break
            if k == 32:                     # SPACE
                enc = _compute_encoding(frame, mp_face, fr, cv2)
                if enc is None:
                    print("no face — try again")
                    continue
                encs.append(enc)
                print(f"captured {len(encs)}/{n_samples}")
    finally:
        cap.release()
        cv2.destroyAllWindows()
    return encs


def _capture_samples_headless(name, n_samples, camera_index, delay_s, deps):
    cv2 = deps["cv2"]
    mp_face = deps.get("mp_face")
    fr = deps["face_recognition"]
    cap = cv2.VideoCapture(camera_index, cv2.CAP_V4L2)
    if not cap.isOpened():
        raise SystemExit(f"camera {camera_index} not available — "
                         "is the daemon holding it open? Try: "
                         "sudo systemctl stop smart-gate")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    print(f"Headless enroll for '{name}' — capturing {n_samples} samples,")
    print(f"{delay_s}s between each. Stand in front of the camera, look")
    print("around slightly to get pose variation.")
    encs = []
    deadline_per_sample_s = max(delay_s * 5, 10.0)
    try:
        for i in range(n_samples):
            if i > 0:
                time.sleep(delay_s)
            print(f"  sample {i+1}/{n_samples}: looking for face...", end="",
                  flush=True)
            start = time.monotonic()
            enc = None
            while time.monotonic() - start < deadline_per_sample_s:
                ok, frame = cap.read()
                if not ok:
                    continue
                enc = _compute_encoding(frame, mp_face, fr, cv2)
                if enc is not None:
                    break
            if enc is None:
                print(f" no face after {deadline_per_sample_s:.0f}s")
                continue
            encs.append(enc)
            print(" ✓")
    finally:
        cap.release()
    return encs


def _find_face_box(rgb, mp_face, fr):
    """Return (x, y, w, h) in rgb pixel coords for the largest face, or None."""
    if mp_face is not None:
        result = mp_face.process(rgb)
        if result.detections:
            h, w = rgb.shape[:2]
            rb = result.detections[0].location_data.relative_bounding_box
            return (int(rb.xmin * w), int(rb.ymin * h),
                    int(rb.width * w), int(rb.height * h))
    locations = fr.face_locations(rgb, model="hog",
                                  number_of_times_to_upsample=1)
    if locations:
        top, right, bottom, left = locations[0]
        return (left, top, right - left, bottom - top)
    return None


def _compute_encoding(bgr, mp_face, fr, cv2):
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    if mp_face is not None:
        result = mp_face.process(rgb)
        if not result.detections:
            return None
        encs = fr.face_encodings(rgb, num_jitters=1)
    else:
        locations = fr.face_locations(rgb, model="hog",
                                      number_of_times_to_upsample=1)
        if not locations:
            return None
        encs = fr.face_encodings(rgb, known_face_locations=locations[:1],
                                 num_jitters=1)
    if not encs:
        return None
    return encs[0]

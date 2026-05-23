"""Enrollment: capture N face samples + insert encodings + signal daemon."""
from __future__ import annotations

import logging
from pathlib import Path
import numpy as np

from smart_gate.cli._signal import signal_daemon
from smart_gate.cli import qr as qr_mod

log = logging.getLogger(__name__)


def enroll(db, name: str, qr_dir: Path, n_samples: int = 5,
           camera_index: int = 0, *, deps=None) -> Path:
    """Returns the path of the generated QR PNG."""
    if deps is None:
        import cv2 as _cv2
        import mediapipe as _mp
        import face_recognition as _fr
        deps = {
            "cv2": _cv2,
            "mp_face": _mp.solutions.face_detection.FaceDetection(
                model_selection=0, min_detection_confidence=0.7),
            "face_recognition": _fr,
        }
    if db.get_user_id_by_name(name) is not None:
        raise SystemExit(f"user already exists: {name}")
    uid = db.insert_user(name)

    encs = _capture_samples(name, n_samples, camera_index, deps)
    if len(encs) < n_samples:
        db.delete_user(name)
        raise SystemExit(f"only captured {len(encs)}/{n_samples} samples; aborted")
    for i, enc in enumerate(encs):
        db.insert_face_encoding(uid, enc.astype("float32").tobytes(), i)

    path = qr_mod.issue_initial(db, name, qr_dir)
    signal_daemon()
    print(f"enrolled {name} ({len(encs)} samples). QR: {path}")
    return path


def _capture_samples(name: str, n_samples: int, camera_index, deps) -> list:
    cv2 = deps["cv2"]
    mp_face = deps["mp_face"]
    fr = deps["face_recognition"]
    # camera_index may be an int (index) or a str (path like /dev/smart-gate-camera);
    # cv2.VideoCapture accepts both.
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
            result = mp_face.process(rgb)
            if result.detections:
                for det in result.detections:
                    rb = det.location_data.relative_bounding_box
                    h, w = frame.shape[:2]
                    x = int(rb.xmin * w); y = int(rb.ymin * h)
                    bw = int(rb.width * w); bh = int(rb.height * h)
                    cv2.rectangle(annotated, (x, y), (x+bw, y+bh), (0, 255, 0), 2)
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


def _compute_encoding(bgr, mp_face, fr, cv2):
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    result = mp_face.process(rgb)
    if not result.detections:
        return None
    encs = fr.face_encodings(rgb, num_jitters=1)
    if not encs:
        return None
    return encs[0]

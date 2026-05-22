"""Recorder: ring buffer of recent JPEGs + ffmpeg clip writer + retention."""
from __future__ import annotations

import collections
import logging
import queue
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class RecordingTrigger:
    event_id: int
    ts_mono: float


class RingBuffer:
    def __init__(self, fps: int = 15, pre_seconds: int = 5):
        self._buf: collections.deque[tuple[float, bytes]] = collections.deque(
            maxlen=fps * pre_seconds
        )
        self._lock = threading.Lock()

    def push(self, jpeg: bytes, ts_mono: float) -> None:
        with self._lock:
            self._buf.append((ts_mono, jpeg))

    def snapshot(self) -> list[tuple[float, bytes]]:
        with self._lock:
            return list(self._buf)


def run_recorder(hub, ring: RingBuffer, trigger_queue: queue.Queue,
                 db, data_dir: Path, cfg, shutdown: threading.Event) -> None:
    """Recorder thread main loop. Pulls triggers from trigger_queue and writes clips.

    Ring buffer is fed by the cap thread (not this thread), so cleanup of the ring
    is not the recorder's concern.
    """
    while not shutdown.is_set():
        try:
            trig = trigger_queue.get(timeout=0.5)
        except queue.Empty:
            continue
        try:
            _record_one(trig, hub, ring, db, data_dir, cfg, shutdown)
        except Exception as e:
            log.exception("recorder failed for event %d: %s", trig.event_id, e)


def _record_one(trig: RecordingTrigger, hub, ring: RingBuffer, db,
                data_dir: Path, cfg, shutdown: threading.Event) -> None:
    clips_dir = Path(data_dir) / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    free = shutil.disk_usage(data_dir).free
    if free < 200 * 1024 * 1024:
        log.error("disk free %d < 200MB, skipping clip for event %d",
                  free, trig.event_id)
        return

    pre = ring.snapshot()
    post: list[tuple[float, bytes]] = []
    deadline = time.monotonic() + cfg.recorder.post_seconds
    while time.monotonic() < deadline and not shutdown.is_set():
        jpg = hub.wait_jpeg(timeout=0.5)
        if jpg is None:
            continue
        post.append((time.monotonic(), jpg))

    with tempfile.TemporaryDirectory(dir=str(data_dir)) as tmp:
        for i, (_, jpg) in enumerate(pre + post):
            (Path(tmp) / f"{i:05d}.jpg").write_bytes(jpg)
        out = clips_dir / f"{trig.event_id}.mp4"
        cmd = [
            "ffmpeg", "-loglevel", "warning",
            "-framerate", str(cfg.video.fps),
            "-i", f"{tmp}/%05d.jpg",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
            "-movflags", "+faststart",
            "-y", str(out),
        ]
        try:
            subprocess.run(cmd, check=True, timeout=cfg.recorder.ffmpeg_timeout_s)
            db.update_event_clip(trig.event_id, f"clips/{trig.event_id}.mp4")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
                FileNotFoundError) as e:
            log.warning("ffmpeg failed for event %d: %s", trig.event_id, e)
            out.unlink(missing_ok=True)


def cleanup_pass(data_dir: str | Path, db, max_age_days: int,
                 max_total_gb: float) -> None:
    """Apply retention policy (E): delete clips older than max_age_days OR
    when total clip storage > max_total_gb. Event rows are preserved.
    """
    data_dir = Path(data_dir)
    cutoff_ts = (datetime.now() - timedelta(days=max_age_days)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    rows = db.events_for_cleanup()
    rows = sorted(rows, key=lambda r: (r[1], r[0]))   # deterministic order
    survivors: list[tuple[int, str, int]] = []

    for ev_id, ts, clip_rel in rows:
        clip_path = data_dir / clip_rel
        if ts < cutoff_ts:
            _delete_clip(data_dir, ev_id, clip_rel, db)
            continue
        if not clip_path.exists():
            log.warning("clip missing for event %d: %s", ev_id, clip_rel)
            db.update_event_clip(ev_id, None)
            continue
        survivors.append((ev_id, clip_rel, clip_path.stat().st_size))

    total = sum(sz for _, _, sz in survivors)
    limit = int(max_total_gb * 1024**3)
    i = 0
    while total > limit and i < len(survivors):
        ev_id, clip_rel, sz = survivors[i]
        _delete_clip(data_dir, ev_id, clip_rel, db)
        total -= sz
        i += 1


def _delete_clip(data_dir: Path, ev_id: int, clip_rel: str, db) -> None:
    path = data_dir / clip_rel
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    db.update_event_clip(ev_id, None)

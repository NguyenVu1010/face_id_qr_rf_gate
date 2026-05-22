"""Recorder + retention.

Phase 1: cleanup_pass (this task).
Phase 2: ring buffer + ffmpeg subprocess (next task).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger(__name__)


def cleanup_pass(data_dir: str | Path, db, max_age_days: int,
                 max_total_gb: float) -> None:
    """Apply retention policy (E): delete clips older than max_age_days OR
    when total clip storage > max_total_gb. Event rows are preserved; only
    files are removed and clip_path NULLed.
    """
    data_dir = Path(data_dir)
    cutoff_ts = (datetime.now() - timedelta(days=max_age_days)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    rows = db.events_for_cleanup()                     # list of (id, ts, clip_path)
    # Stable oldest-first ordering even when ts strings tie (same-second inserts).
    rows = sorted(rows, key=lambda r: (r[1], r[0]))
    survivors: list[tuple[int, str, int]] = []         # (id, clip_path, size)

    # Phase 1: drop by age, also drop rows whose file is missing
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

    # Phase 2: size limit (delete oldest survivors first; rows are already ts ASC)
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

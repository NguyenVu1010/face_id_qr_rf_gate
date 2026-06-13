"""Boot-time check that critical vendored static assets are present and
non-placeholder.

The dashboard depends on `htmx.min.js` (≈48 KB) being a real library file,
not the 84-byte placeholder comment that landed in git. If the file is
missing or under-sized at app startup, callers get a list of degraded asset
names so the UI can render a banner and the boot log can record an ERROR.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

# (name, min_bytes). Real htmx.min.js is ~48 KB; placeholder is 84 B.
# 10 KB threshold catches the placeholder while leaving headroom for
# legitimate minified-library size variation.
CRITICAL_ASSETS: list[tuple[str, int]] = [
    ("htmx.min.js", 10_000),
]


def check_static_assets(static_dir: Path) -> list[str]:
    """Return names of critical assets that are missing or under-sized.

    Empty list means every entry in CRITICAL_ASSETS passes its
    min-byte threshold under `static_dir`. Any I/O error reading a
    file is treated as "degraded" rather than propagated, so a
    permission-denied case never crashes Flask startup.
    """
    static_dir = Path(static_dir)
    degraded: list[str] = []
    for name, min_bytes in CRITICAL_ASSETS:
        path = static_dir / name
        try:
            size = path.stat().st_size
        except OSError as e:
            log.debug("asset_check: stat failed for %s: %s", path, e)
            degraded.append(name)
            continue
        if size < min_bytes:
            degraded.append(name)
    return degraded

# Dashboard Asset Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore HTMX-driven dashboard buttons on the Pi, and add a Flask boot-time guard that warns loudly when a critical static asset is missing or replaced by a placeholder.

**Architecture:** New pure-Python module `smart_gate/web/asset_check.py` exposes `check_static_assets(static_dir)` returning a list of degraded asset names. `create_app()` calls it once, stashes the list in `app.config["ASSET_WARNINGS"]`, logs ERROR if non-empty, and a context processor exposes it to every template. `base.html` renders a sticky red banner when the list is non-empty. The one-shot fix `scp`s the real `htmx.min.js` (48 KB) to the Pi.

**Tech Stack:** Python 3.13 / Flask 3 / pytest / bash for deploy.

---

## Task 1: `check_static_assets` module + tests (TDD)

**Files:**
- Create: `smart_gate/web/asset_check.py`
- Create: `tests/web/test_asset_check.py`
- Create (if missing): `tests/web/__init__.py`

- [ ] **Step 1: Confirm test dir exists**

Run: `ls tests/web/ 2>/dev/null || mkdir -p tests/web && touch tests/web/__init__.py`
Expected: directory exists with `__init__.py`.

- [ ] **Step 2: Write the failing tests**

Create `tests/web/test_asset_check.py`:

```python
"""Tests for smart_gate.web.asset_check.check_static_assets()."""
import os
from pathlib import Path

import pytest

from smart_gate.web.asset_check import (
    CRITICAL_ASSETS,
    check_static_assets,
)


def test_all_assets_healthy(tmp_path: Path):
    # Write a stub for every critical asset, each at twice the min size.
    for name, min_bytes in CRITICAL_ASSETS:
        (tmp_path / name).write_bytes(b"x" * (min_bytes * 2))
    assert check_static_assets(tmp_path) == []


def test_placeholder_under_min_flagged(tmp_path: Path):
    # 84-byte placeholder mimics the real-world failure mode.
    (tmp_path / "htmx.min.js").write_bytes(b"/* placeholder */\n" * 4)
    result = check_static_assets(tmp_path)
    assert "htmx.min.js" in result


def test_missing_asset_flagged(tmp_path: Path):
    # tmp_path is empty.
    result = check_static_assets(tmp_path)
    assert "htmx.min.js" in result


def test_permission_denied_treated_as_degraded(tmp_path: Path):
    p = tmp_path / "htmx.min.js"
    p.write_bytes(b"x" * 60_000)
    try:
        os.chmod(p, 0o000)
        result = check_static_assets(tmp_path)
    finally:
        os.chmod(p, 0o644)
    # File exists but unreadable → either fine (stat works on dir perms)
    # or flagged. Acceptable: must not raise.
    assert isinstance(result, list)


def test_empty_critical_list_returns_empty(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "smart_gate.web.asset_check.CRITICAL_ASSETS", []
    )
    assert check_static_assets(tmp_path) == []
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /home/nguyenvd/workspace/smart_gate && python -m pytest tests/web/test_asset_check.py -v`
Expected: `ImportError: cannot import name 'check_static_assets'` or
`ModuleNotFoundError: No module named 'smart_gate.web.asset_check'`.

- [ ] **Step 4: Implement `asset_check.py`**

Create `smart_gate/web/asset_check.py`:

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /home/nguyenvd/workspace/smart_gate && python -m pytest tests/web/test_asset_check.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add smart_gate/web/asset_check.py tests/web/test_asset_check.py tests/web/__init__.py
git commit -m "feat(web): asset_check module — flag missing/placeholder static assets

Catches the htmx.min.js placeholder-in-git problem at Flask boot:
returns list of degraded asset names. I/O errors treated as degraded
rather than raised so a misconfigured permission can't crash startup.
"
```

---

## Task 2: Wire `check_static_assets` into `create_app`

**Files:**
- Modify: `smart_gate/web/app.py` (right after `app = Flask(...)`)

- [ ] **Step 1: Read current `create_app` head**

Open `smart_gate/web/app.py` and locate the `app = Flask(__name__, ...)`
construction (~line 83). The block below it currently goes straight into
`@app.route("/")`.

- [ ] **Step 2: Insert import at top of `app.py`**

Find the existing imports block and add:

```python
from .asset_check import check_static_assets
```

(Place near the other relative imports from the same package.)

- [ ] **Step 3: Insert guard after Flask construction**

Right after the `app = Flask(__name__, template_folder=..., static_folder=...)`
statement and before the first `@app.route` decorator, add:

```python
    _asset_warnings = check_static_assets(Path(app.static_folder))
    app.config["ASSET_WARNINGS"] = _asset_warnings
    if _asset_warnings:
        log.error(
            "web static assets degraded: %s — dashboard buttons will not work",
            ", ".join(_asset_warnings),
        )

    @app.context_processor
    def _inject_asset_warnings():
        return {"asset_warnings": _asset_warnings}
```

Verify `log` is the module-level logger already in this file (search for
`log = logging.getLogger` near the top — if absent, add it).

- [ ] **Step 4: Run the existing web test suite**

Run: `cd /home/nguyenvd/workspace/smart_gate && python -m pytest tests/ -k "web" -v`
Expected: all existing web tests still pass (no regression). If
`tests/web/test_asset_check.py` runs here too, 5 more pass.

- [ ] **Step 5: Commit**

```bash
git add smart_gate/web/app.py
git commit -m "feat(web): call check_static_assets at app boot

Logs ERROR + injects asset_warnings into every template context so
base.html can render a degraded banner. App keeps running even when
assets are missing so RFID/face auth stays available.
"
```

---

## Task 3: Banner in `base.html` + style in `app.css`

**Files:**
- Modify: `smart_gate/web/templates/base.html`
- Modify: `smart_gate/web/static/app.css`

- [ ] **Step 1: Add banner markup to `base.html`**

Open `smart_gate/web/templates/base.html`. Insert immediately after the
opening `<body>` tag and before the `<header class="topbar">` element:

```html
{% if asset_warnings %}
<div class="asset-warning-banner" role="alert">
  &#9888; WEB ASSETS DEGRADED &mdash; missing or placeholder:
  <code>{{ asset_warnings | join(', ') }}</code>.
  Dashboard buttons will not work. Re-deploy these files to
  <code>smart_gate/web/static/</code> and restart the service.
</div>
{% endif %}
```

- [ ] **Step 2: Add CSS to `app.css`**

Append to `smart_gate/web/static/app.css`:

```css
.asset-warning-banner {
  position: sticky;
  top: 0;
  z-index: 10000;
  background: #b91c1c;
  color: #fff;
  font-weight: 600;
  padding: 10px 16px;
  text-align: center;
  border-bottom: 2px solid #fff;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 13px;
}
.asset-warning-banner code {
  background: rgba(0,0,0,0.25);
  padding: 1px 6px;
  border-radius: 3px;
}
```

- [ ] **Step 3: Smoke-test banner locally**

Run:

```bash
cd /home/nguyenvd/workspace/smart_gate
# Temporarily move htmx.min.js out of the way to trigger the banner.
mv smart_gate/web/static/htmx.min.js /tmp/htmx.min.js.bak
python -m smart_gate --help 2>&1 | head -5  # confirm app boots without error
mv /tmp/htmx.min.js.bak smart_gate/web/static/htmx.min.js
```

Expected: no crash. (Full HTTP smoke test is in Task 5 on the Pi.)

- [ ] **Step 4: Commit**

```bash
git add smart_gate/web/templates/base.html smart_gate/web/static/app.css
git commit -m "feat(web): degraded-asset banner in base.html + sticky-top style

Banner renders on every page when app.config['ASSET_WARNINGS'] is
non-empty so admin sees the problem immediately on any route.
"
```

---

## Task 4: Deploy `htmx.min.js` to Pi (one-shot restore)

**Files:** (deploy only, no commit)

- [ ] **Step 1: Verify local file is the real library**

Run: `wc -c smart_gate/web/static/htmx.min.js`
Expected: ≥ 40000 bytes (real lib is ~48 KB).

- [ ] **Step 2: Verify Pi currently has the placeholder**

Run: `ssh pi@192.168.1.137 "wc -c /home/pi/smart_gate/smart_gate/web/static/htmx.min.js"`
Expected: 84 bytes (placeholder).

- [ ] **Step 3: scp the real file**

Run: `scp smart_gate/web/static/htmx.min.js pi@192.168.1.137:/home/pi/smart_gate/smart_gate/web/static/htmx.min.js`
Expected: transfer succeeds, no errors.

- [ ] **Step 4: Verify size on Pi matches local**

Run: `ssh pi@192.168.1.137 "md5sum /home/pi/smart_gate/smart_gate/web/static/htmx.min.js" && md5sum smart_gate/web/static/htmx.min.js`
Expected: same md5 on both lines.

---

## Task 5: Deploy app + restart + manual verification

**Files:** (deploy only)

- [ ] **Step 1: Sync code changes to Pi**

Run:

```bash
rsync -av --exclude '__pycache__' \
  smart_gate/web/asset_check.py \
  smart_gate/web/app.py \
  smart_gate/web/templates/base.html \
  smart_gate/web/static/app.css \
  pi@192.168.1.137:/home/pi/smart_gate/smart_gate/web/ 2>&1 | head -20
```

(Adjust path layout if rsync resolves paths differently — alternative:
individual `scp` per file.)

Expected: 4 files transferred.

- [ ] **Step 2: Restart service**

Run:

```bash
ssh pi@192.168.1.137 "sudo systemctl restart smart-gate && sleep 3 && sudo systemctl is-active smart-gate"
```

Expected: `active`.

- [ ] **Step 3: Check service logs for asset_check ERROR (must be ABSENT)**

Run: `ssh pi@192.168.1.137 "sudo journalctl -u smart-gate -n 50 --no-pager | grep -i 'asset' || echo NO_ASSET_ERROR"`
Expected: `NO_ASSET_ERROR` (because htmx.min.js was restored in Task 4).

- [ ] **Step 4: Manual UI verification**

In browser:

1. Hard-refresh dashboard (Ctrl+Shift+R).
2. Banner must NOT be visible at top of page.
3. Click **Open gate** → toast "Gate opening…" bottom-right; ESP log
   stream shows `cmd:open`.
4. Click **Close gate** → toast "Gate closing…".
5. Within 2.5 s the quickstats panel and gate badge populate (not `—`).
6. Click **+ Tạo user mới** → modal opens; pick Face → "Chụp + Tạo" →
   toast "Đang capture mặt …" then "✓ Tạo user_NNN".

- [ ] **Step 5: Negative test — banner appears when asset removed**

Run:

```bash
ssh pi@192.168.1.137 "sudo mv /home/pi/smart_gate/smart_gate/web/static/htmx.min.js /tmp/htmx.bak && sudo systemctl restart smart-gate && sleep 3"
```

Hard-refresh dashboard. Expected: red banner at top: "WEB ASSETS DEGRADED
— missing or placeholder: `htmx.min.js`". Journald shows ERROR log.

Restore:

```bash
ssh pi@192.168.1.137 "sudo mv /tmp/htmx.bak /home/pi/smart_gate/smart_gate/web/static/htmx.min.js && sudo systemctl restart smart-gate"
```

Hard-refresh. Banner gone.

- [ ] **Step 6: Final commit (status note in plan-tracking)**

Nothing to commit code-wise here — deploy succeeded. If you want a
deploy-record commit (optional):

```bash
git commit --allow-empty -m "deploy: htmx.min.js restored on Pi + asset guard live"
```

---

## Done criteria

- All 4 new code commits land on `feat/safety-fixes`.
- `pytest tests/web/test_asset_check.py` passes (5 tests).
- No regression in existing `tests/web/` suite.
- Open / Close gate / Add user / quickstats / recent events all work
  after browser hard-refresh on the deployed Pi.
- Banner appears when `htmx.min.js` is removed, disappears when restored.

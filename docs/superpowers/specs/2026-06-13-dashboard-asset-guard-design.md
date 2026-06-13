# Dashboard Asset Guard — Design Spec

**Date:** 2026-06-13
**Branch:** `feat/safety-fixes`
**Status:** Approved

## Problem

All HTMX-driven dashboard buttons (Open gate, Close gate) and polling widgets
(quickstats, recent events, gate badge) silently fail on the deployed Pi. Root
cause: `smart_gate/web/static/htmx.min.js` on the Pi (file dated May 23, 84
bytes) contains only the placeholder comment:

```
/* download htmx from https://unpkg.com/htmx.org/dist/htmx.min.js into this file */
```

The real HTMX library (≈48 KB) was never vendored on the Pi. Local
`htmx.min.js` (48,101 bytes) is intact. Backend API endpoints work — `curl -X
POST /api/gate/open` returns 200 — so the failure is purely client-side and
silent (no error toast, no console message visible to the user).

The Add-user button uses pure JS `addEventListener` so it is unaffected by
HTMX, but its markup was only deployed in the immediately prior turn, which is
why the user noticed all three buttons together.

## Goals

1. Restore HTMX behavior on the Pi (immediate fix).
2. Prevent recurrence: if a critical static asset is missing or under-sized at
   Flask startup, log an ERROR and surface a banner on every page so the
   admin cannot miss the degraded state.

Non-goals: redesigning the deploy pipeline, switching to CDN-loaded HTMX,
adding generic asset versioning. Banner is local-LAN admin tooling; no i18n,
no styling polish beyond legibility.

## Architecture

Two independent pieces:

### Piece 1 — One-shot restore

- `scp` local `htmx.min.js` (48 KB) to Pi at
  `/home/pi/smart_gate/smart_gate/web/static/htmx.min.js`
- `sudo systemctl restart smart-gate`
- User hard-refreshes browser (Ctrl+Shift+R)
- Verify: click Open gate → HTMX toast "Gate opening…" → ESP receives
  `cmd:open` (visible in toast stack from SSE log)

### Piece 2 — Asset guard (Flask-side)

```
smart_gate/web/asset_check.py     (NEW, ~30 LOC)
smart_gate/web/app.py             (MODIFY, ~6 LOC at create_app)
smart_gate/web/templates/base.html (MODIFY, ~7 LOC banner block)
tests/web/test_asset_check.py     (NEW, ~50 LOC)
```

**Module `asset_check.py`:**

```python
CRITICAL_ASSETS: list[tuple[str, int]] = [
    ("htmx.min.js", 10_000),  # real lib ≈48 KB; placeholder is 84 B
]

def check_static_assets(static_dir: Path) -> list[str]:
    """Return list of degraded asset paths (under-size or missing).

    Empty list means all critical assets pass their min-size threshold.
    """
```

Logic:
- For each `(name, min_bytes)` in `CRITICAL_ASSETS`:
  - Resolve `static_dir / name`
  - If file missing → append path, continue
  - `os.stat(path).st_size < min_bytes` → append path
- Any I/O error (`OSError`) is caught and the file is treated as degraded;
  no propagation to crash Flask startup.
- Returns list of relative names (e.g. `["htmx.min.js"]`) for display.

**Integration in `create_app()` (`smart_gate/web/app.py`):**

Right after `app = Flask(__name__, ...)`, before route registration:

```python
warnings = check_static_assets(Path(app.static_folder))
app.config["ASSET_WARNINGS"] = warnings
if warnings:
    log.error("web static assets degraded: %s — dashboard will not function",
              ", ".join(warnings))

@app.context_processor
def _inject_asset_warnings():
    return {"asset_warnings": warnings}
```

The context processor exposes the list to every template without each route
having to pass it explicitly.

**Banner in `base.html`:**

Insert immediately after `<body>` opening (before `<header class="topbar">`):

```html
{% if asset_warnings %}
<div class="asset-warning-banner" role="alert">
  &#9888; WEB ASSETS DEGRADED — missing/placeholder:
  <code>{{ asset_warnings | join(', ') }}</code> &mdash;
  dashboard buttons will not work. Re-deploy these files.
</div>
{% endif %}
```

Inline style kept terse (red bg, white text, bold, sticky-top) — added to
`app.css`. No new template fragment file.

### Decision: warn vs. abort

Banner-only, do not abort startup. Smart-gate must stay up to handle RFID /
face / serial — the dashboard is admin convenience. A degraded dashboard
should not take down RFID auth. The banner is visible on every page so admin
cannot miss it; the ERROR log is captured by journald.

## Testing

### Unit (`tests/web/test_asset_check.py`)

| Case                                | Setup                          | Expected return                |
|-------------------------------------|--------------------------------|--------------------------------|
| All assets healthy                  | tmpdir + 50 KB stub file       | `[]`                           |
| Placeholder htmx (under min)        | tmpdir + 84-byte stub          | `["htmx.min.js"]`              |
| Missing htmx                        | tmpdir empty                   | `["htmx.min.js"]`              |
| Permission denied on file           | tmpdir + chmod 000 stub        | `["htmx.min.js"]` (no raise)   |

Use `tmp_path` pytest fixture. No mocking — real filesystem, real `os.stat`.

### Manual verification

After deploy + restart on Pi:

1. **Banner test:** Move `htmx.min.js` aside on Pi; restart service;
   open dashboard; banner must be visible at top; journald must contain
   `web static assets degraded: htmx.min.js`; restore file; restart;
   banner gone.
2. **Buttons test:** Hard-refresh dashboard; click **Open gate** →
   toast "Gate opening…" must appear bottom-right; ESP log stream
   should show `cmd:open` arrived.
3. **Polling test:** Within 2.5 s the quickstats panel and gate-badge
   should populate (not stay as `—`).
4. **Add user:** Click "+ Tạo user mới" → modal opens → Face mode →
   "Chụp + Tạo" → toast "Đang capture mặt — đứng yên ~2s" then
   "✓ Tạo user_NNN".

## Error handling

- File missing or under-sized: log ERROR, banner shown, app keeps running.
- I/O error (permission, race): same treatment as under-sized.
- Empty `CRITICAL_ASSETS` list: `check_static_assets()` returns `[]`,
  no banner — safe default if all entries are removed later.

## Files touched

| Path                                              | Action   | LOC      |
|---------------------------------------------------|----------|----------|
| `smart_gate/web/asset_check.py`                   | Create   | ~30      |
| `tests/web/test_asset_check.py`                   | Create   | ~50      |
| `smart_gate/web/app.py`                           | Modify   | ~6       |
| `smart_gate/web/templates/base.html`              | Modify   | ~7       |
| `smart_gate/web/static/app.css`                   | Modify   | ~8       |
| `/home/pi/.../static/htmx.min.js` (Pi only, scp)  | Replace  | (binary) |

## Rollout

1. Implement + test locally (pytest passes).
2. Commit.
3. `scp` `htmx.min.js` to Pi (this fixes existing breakage immediately).
4. Rsync code changes to Pi.
5. `sudo systemctl restart smart-gate` on Pi.
6. Manual verification list above.

## Open questions

None. The placeholder comment in the existing file makes the intent
unambiguous (vendored copy was always the plan; the dev never finished the
download step).

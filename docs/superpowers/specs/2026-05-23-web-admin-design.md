# Smart Gate — Web Admin Design Spec

**Date:** 2026-05-23
**Status:** Design draft awaiting review
**Branch:** `feat/web-admin`
**Scope:** Polish and expansion of the Flask web admin (`smart_gate/web/`). Consumes
[2026-05-22-pi-app-design.md](2026-05-22-pi-app-design.md) §8 (web admin baseline) as the
contract for routes already in place. This doc adds two new pages (`/events`, `/system`),
replaces Pico.css with a small custom design system, adds a live ESP32 log stream via
Server-Sent Events, and refines the dashboard. **No backend invariants change** — same
threading model, same UART protocol, same recorder, same recognition pipeline, same DB
schema. The only backend additions are: an in-memory `EspLogBus` pub/sub, two DB helper
extensions, one route group (system/events + SSE), and HTML-fragment variants of
`/events.json` and `/healthz`.

**Definition of done:** all four pages render with the new design system, link/FPS/frame-age
status pills update live, dashboard event list and full-page event list both auto-refresh,
clip modal plays mp4 from `/clips/<id>.mp4`, `/system` shows live-streaming ESP32 log via SSE
with reconnect-resume, link-down banner appears within 3 s of UART disconnect, and existing
integration tests still pass.

---

## 1. Overview

### 1.1 Audience & priorities

The admin is a **desktop-first dev console and demo surface** — not a kiosk. Density,
technical detail (FPS, frame age, ESP32 log, link state), and visual polish all matter;
"readable from across the room" does not. Single concurrent user is the design point;
multi-user is out of scope.

### 1.2 Stack chosen

| Layer | Choice | Note |
|---|---|---|
| Server | Flask + Jinja2 | unchanged |
| Live transport | HTMX 1.9 polling + native EventSource (SSE) for ESP32 log | mostly HTMX; SSE only where polling would be wasteful (log lines arrive sparsely & need ordering) |
| CSS | One hand-written file `static/app.css`, ~500 LOC | **Pico.css removed** |
| Client JS | One hand-written file `static/app.js`, ~30 LOC | clip modal, toast on gate-action error, SSE bootstrap |

### 1.3 File changes

```
smart_gate/web/
├── app.py                          [MODIFY] +5 routes, dep injection of esp_log_bus
├── templates/
│   ├── base.html                   [REWRITE] top bar, nav, link-down banner, status pills
│   ├── dashboard.html              [REWRITE]
│   ├── events.html                 [NEW]
│   ├── users.html                  [REWRITE]
│   ├── system.html                 [NEW]
│   └── _partials/                  [NEW DIR]
│       ├── event_rows.html         fragment for /events.json?format=html (filter-aware)
│       ├── statusbar.html          fragment for /healthz?format=html
│       └── esp_log_line.html       single <li> rendering for SSE + initial backfill
└── static/
    ├── app.css                     [NEW]
    ├── app.js                      [NEW]
    ├── htmx.min.js                 [KEEP]
    └── pico.min.css                [DELETE]

smart_gate/link/
└── esp_log_bus.py                  [NEW] in-memory pub/sub for ESP32 log events

smart_gate/data/
└── db.py                           [MODIFY]
    - recent_events(): add method/granted/q/before_id filter params
    - insert_esp_log(): return inserted id
    - recent_esp_log(limit, after_id): NEW
    - count_events_today(): NEW (for dashboard quick stats)

smart_gate/main.py                  [MODIFY]
    - construct EspLogBus, pass into _consume_bus and _run_web
    - _handle_esp_event(v=log): publish to bus AFTER insert (with returned id)

tests/
├── unit/
│   ├── test_db.py                  [MODIFY] + filter-param tests
│   └── test_esp_log_bus.py         [NEW]
└── integration/
    └── test_web.py                 [NEW] route smoke + SSE round-trip
```

---

## 2. Visual design system (`static/app.css`)

Tokens go in `:root` as CSS custom properties so a future dark-mode toggle is a
one-class-on-`<body>` change without touching markup.

### 2.1 Color tokens

```css
:root {
  /* Surfaces */
  --bg:          #ffffff;
  --surface-1:  #f8fafc;     /* page background, subtle gray */
  --surface-2:  #f1f5f9;     /* nested panels, hover */
  --surface-3:  #e2e8f0;     /* deepest fill (skeleton, divider strong) */
  --border:     #e2e8f0;
  --border-strong: #cbd5e1;

  /* Text */
  --text-1:     #0f172a;     /* primary */
  --text-2:     #475569;     /* secondary */
  --text-3:     #94a3b8;     /* tertiary, captions */

  /* Brand */
  --accent:        #6366f1;  /* indigo-500 */
  --accent-hover:  #4f46e5;
  --accent-bg:     #eef2ff;
  --accent-fg:     #ffffff;

  /* Semantic (status) */
  --ok:        #16a34a;  --ok-bg:        #dcfce7;
  --warn:      #d97706;  --warn-bg:      #fef3c7;
  --danger:    #dc2626;  --danger-bg:    #fee2e2;
  --info:      #2563eb;  --info-bg:      #dbeafe;

  /* Method pills */
  --pill-face-fg:  #166534;  --pill-face-bg:  #dcfce7;
  --pill-qr-fg:    #1e40af;  --pill-qr-bg:    #dbeafe;
  --pill-rfid-fg:  #6b21a8;  --pill-rfid-bg:  #f3e8ff;
  --pill-manual-fg:#475569;  --pill-manual-bg:#f1f5f9;
  --pill-deny-fg:  #991b1b;  --pill-deny-bg:  #fee2e2;

  /* Shadows */
  --shadow-sm: 0 1px 2px rgba(15,23,42,0.05);
  --shadow-md: 0 4px 12px rgba(15,23,42,0.08);
  --shadow-lg: 0 12px 32px rgba(15,23,42,0.14);

  /* Radii */
  --r-sm: 4px;  --r-md: 6px;  --r-lg: 10px;  --r-pill: 999px;

  /* Spacing (4-pt grid) */
  --s-1: 4px;  --s-2: 8px;  --s-3: 12px;  --s-4: 16px;
  --s-5: 24px; --s-6: 32px; --s-7: 48px;

  /* Type */
  --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
               "Helvetica Neue", Arial, sans-serif;
  --font-mono: ui-monospace, "SF Mono", "JetBrains Mono", "Menlo",
               "Consolas", monospace;

  /* Layout */
  --content-max: 1280px;
  --topbar-h: 52px;
}
```

### 2.2 Type scale

| Token | Size / line | Use |
|---|---|---|
| `--fs-xs` | 11 / 1.4 | meta labels, captions |
| `--fs-sm` | 13 / 1.5 | tertiary text, table cells |
| `--fs-base` | 14 / 1.55 | body |
| `--fs-md` | 16 / 1.5 | page subheaders |
| `--fs-lg` | 20 / 1.4 | page H1 |
| `--fs-xl` | 28 / 1.3 | hero stat number |

Weights used: 400, 500, 600, 700. Monospace is used for: timestamps, event IDs, FPS
numbers, frame age, ESP32 log messages, healthz JSON.

### 2.3 Component primitives

CSS-only, no JS dependency:

- **`.card`** — white surface, 1px border, --r-lg, optional --shadow-sm
- **`.card-header`** — flex row, padding s-3 s-4, border-bottom, h6 + actions
- **`.btn`** — base button, padding s-2 s-4, --r-md, transition 120ms
- **`.btn-primary`** — accent bg, white fg, hover darker
- **`.btn-secondary`** — surface-1 bg, text-1 fg, border
- **`.btn-ghost`** — transparent bg, text-2 fg, hover surface-1
- **`.pill`** — inline-flex, padding 2px 8px, --r-pill, --fs-xs, font-weight 600;
  modifiers `.pill-face .pill-qr .pill-rfid .pill-manual .pill-deny .pill-ok .pill-warn .pill-danger`
- **`.dot`** — 8px circle, modifiers `.dot-ok .dot-warn .dot-danger` (used inside status pills)
- **`.table`** — full-width, --fs-sm, alternating row background --surface-1, mono cells get `font-family: var(--font-mono)`
- **`.input`, `.select`** — standard form controls, matching --r-md
- **`.banner`** — full-width bar above content, modifiers `.banner-warn .banner-danger`
- **`.toast-wrap`** — fixed bottom-right container that stacks active toasts (created once by `app.js`)
- **`.toast`** — single toast inside `.toast-wrap`, --shadow-lg, fade in/out via CSS transition + `.toast-show` class; modifiers `.toast-ok .toast-danger .toast-info`
- **`.dialog`** — `<dialog>` element styling: white surface, --r-lg, --shadow-lg, backdrop with backdrop-filter:blur(2px)

### 2.4 No icon library

Use unicode/UTF-8 symbols (●, ✓, ✗, ▶, ⏵, ⏹, →, ⏵, ⚠, ⓘ) or inline SVG when needed.
No SVG icon set; no font-awesome. The brand mark in the top-bar is a ◆ character
followed by the wordmark.

---

## 3. Layout & navigation (`base.html`)

### 3.1 Shell

```
┌───────────────────────────────────────────────────────────────────────────┐
│  ◆ smart_gate    Dashboard  Events  Users  System    [●LINK] 14fps 0.18s │  ← top bar (sticky)
├───────────────────────────────────────────────────────────────────────────┤
│  ⚠ Link down — UART silent > 30s. Manual gate commands disabled.         │  ← banner (conditional)
├───────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│                       {% block body %}{% endblock %}                      │  ← page content
│                       max-width: 1280px, centered                          │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Top bar (sticky, height 52px)

Three flex groups left-to-right:
1. **Brand**: `◆ smart_gate` — link to `/`
2. **Nav**: Dashboard, Events, Users, System — `.nav-link`, current page gets `.nav-link.on` (text-1 + 2px bottom border accent)
3. **Live status pills** (right-aligned):
   - `[●LINK]` — green dot + "LINK" if `link_alive`, amber dot + "LINK" + tooltip if down
   - `14 fps` — mono, recent cap FPS; amber if < 8, red if 0
   - `0.18s` — mono, last frame age; red if > 5s

The whole status group is wrapped in a fragment and replaced every 2.5 s:
```html
<div id="statusbar"
     hx-get="/healthz?format=html&panel=statusbar"
     hx-trigger="every 2.5s"
     hx-swap="outerHTML">
  {% include "_partials/statusbar.html" %}
</div>
```

### 3.3 Link-down banner

```html
<div id="link-banner"
     hx-get="/healthz?format=html&panel=banner"
     hx-trigger="every 5s"
     hx-swap="outerHTML">
  {% include "_partials/banner.html" %}  {# empty if link_alive #}
</div>
```

The server's `_partials/banner.html` renders empty (`<div id="link-banner"></div>`) when
the link is alive and the full banner when down. This keeps the swap idempotent.

### 3.4 Navigation routes

| Path | Title | Description |
|---|---|---|
| `/` | Dashboard | live stream + quick stats + recent events |
| `/events` | Events | filterable full-history table + clip modal |
| `/users` | Users | enrolled users (read-only) |
| `/system` | System | health JSON + live ESP32 log + diag actions |

---

## 4. Dashboard (`/` — `dashboard.html`)

### 4.1 Layout

Two-column grid, 7fr / 5fr at ≥ 1100px, single column below.

```
┌─────────────────────────────────────────┬────────────────────────────────┐
│ Live preview                            │ Quick stats                    │
│ ┌─────────────────────────────────────┐ │ ┌───────┬───────┬───────────┐ │
│ │                                     │ │ │  14   │  9.1  │   0.18s   │ │
│ │           MJPEG stream              │ │ │cap fps│det fps│ frame age │ │
│ │                                     │ │ ├───────┼───────┼───────────┤ │
│ │                                     │ │ │  37   │ alice │  14:02:09 │ │
│ │                                     │ │ │today  │ last  │  last ts  │ │
│ └─────────────────────────────────────┘ │ └───────┴───────┴───────────┘ │
│ ┌──────────────────┬──────────────────┐ │                                │
│ │   ⏵ Open gate   │   ⏹ Close gate  │ │ Recent events       View all → │
│ └──────────────────┴──────────────────┘ │ ┌────────────────────────────┐ │
│                                         │ │ 14:02:09 face  alice    ✓ │ │
│                                         │ │ 14:01:51 rfid  bob      ✓ │ │
│                                         │ │ 14:01:30 face  —      ✗ │ │
│                                         │ │ 14:00:12 qr    carol    ✓ │ │
│                                         │ │ 13:59:48 face  alice    ✓ │ │
│                                         │ │ … (10 rows)               │ │
│                                         │ └────────────────────────────┘ │
└─────────────────────────────────────────┴────────────────────────────────┘
```

### 4.2 Stream card

```html
<article class="card stream-card">
  <header class="card-header">
    <h3>Live preview</h3>
    <span class="pill pill-ok"><span class="dot dot-ok"></span> live</span>
  </header>
  <div class="stream-wrap">
    <img src="/stream.mjpeg" alt="live"/>
    <!-- "Camera offline" overlay shown via CSS when img has no src or load error -->
  </div>
  <footer class="card-footer stream-actions">
    <button class="btn btn-primary"
            hx-post="/api/gate/open"
            hx-swap="none"
            data-toast-ok="Gate opening…"
            data-toast-err="Gate command failed">
      ⏵ Open gate
    </button>
    <button class="btn btn-secondary"
            hx-post="/api/gate/close"
            hx-swap="none"
            data-toast-ok="Gate closing…"
            data-toast-err="Gate command failed">
      ⏹ Close gate
    </button>
  </footer>
</article>
```

The HTMX `hx-swap="none"` is paired with a global `htmx:afterRequest` listener in
`app.js` that reads `data-toast-ok` / `data-toast-err` off the triggering element and
shows the matching toast. (~10 lines of JS, see §10 for the full app.js.)

### 4.3 Quick stats (right column top)

Six stat tiles in a 3×2 grid:
| Tile | Source | Format |
|---|---|---|
| cap fps | `/healthz` → `cap_fps` (added) | mono number |
| det fps | `/healthz` → `det_fps` (added) | mono number |
| frame age | `/healthz` → `last_frame_ago_s` | "0.18s", red if > 5 |
| events today | `/healthz` → `events_today` (added) | mono number |
| last grant | `/healthz` → `last_grant.name` (added) | text or "—" |
| last grant ts | `/healthz` → `last_grant.ts` (added) | "14:02:09" |

`/healthz?format=html&panel=quickstats` returns just this 3×2 grid; HTMX swaps every
2.5 s (same cadence as the topbar).

### 4.4 Recent events (right column bottom)

Same 10-row table HTMX-polls `/events.json?format=html&limit=10` every 2 s. Uses
`hx-swap="innerHTML"` on the `<tbody>` — same pattern that already exists in the
current dashboard. "View all →" link goes to `/events`.

---

## 5. Events page (`/events` — `events.html`)

### 5.1 Layout

```
┌───────────────────────────────────────────────────────────────────────────┐
│ Events                                                                    │
│                                                                           │
│ Method:  [face] [qr] [rfid] [manual]   ← toggle pills, multi-select       │
│ Result:  ( ) all  (•) granted  ( ) denied                                 │
│ User:    [  ___________  q  ]   Period: [Today ▾]                         │
│                                                                           │
│ ┌─────────────────────────────────────────────────────────────────────┐  │
│ │ Time      Method  User    OK  Clip  Detail                           │  │
│ ├─────────────────────────────────────────────────────────────────────┤  │
│ │ 14:02:09  face    alice   ✓   ▶    {"distance":0.41}                │  │
│ │ 14:01:51  rfid    bob     ✓   ▶    {"uid":"0xABCDEF"}               │  │
│ │ …                                                                    │  │
│ │ 12:00:00  face    —     ✗   —    {"distance":0.78}                │  │
│ └─────────────────────────────────────────────────────────────────────┘  │
│            [ Load 50 older ]                                              │
└───────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Filter form

```html
<form id="event-filter"
      hx-get="/events.json?format=html"
      hx-trigger="change, keyup changed delay:300ms from:input[name=q]"
      hx-target="#events-tbody"
      hx-swap="innerHTML">
  <fieldset class="filter-pills">
    {% for m in ["face","qr","rfid","manual"] %}
    <label class="pill-toggle">
      <input type="checkbox" name="method" value="{{m}}"
             {% if m in selected_methods %}checked{% endif %}>
      <span class="pill pill-{{m}}">{{m}}</span>
    </label>
    {% endfor %}
  </fieldset>

  <fieldset class="filter-radio">
    <label><input type="radio" name="granted" value="" checked> all</label>
    <label><input type="radio" name="granted" value="1"> granted</label>
    <label><input type="radio" name="granted" value="0"> denied</label>
  </fieldset>

  <input type="search" class="input" name="q" placeholder="user name…">

  <select class="select" name="period">
    <option value="today">Today</option>
    <option value="7d">Last 7 days</option>
    <option value="30d">Last 30 days</option>
    <option value="all">All time</option>
  </select>
</form>
```

### 5.3 Auto-refresh and pagination

Two HTMX behaviours on `#events-tbody`:

1. **Initial + filter change**: form `hx-get` replaces tbody innerHTML (see above).
2. **Live prepend**: a separate `<div id="events-live">` polls the same endpoint
   every 2 s. It uses HTMX's `hx-include` to inherit the form's filter values and
   `hx-vals='js:{after_id: maxEventId()}'` to compute the latest seen id at request
   time:

   ```html
   <div id="events-live"
        hx-get="/events.json?format=html"
        hx-include="#event-filter"
        hx-vals='js:{after_id: maxEventId()}'
        hx-trigger="every 2s"
        hx-target="#events-tbody"
        hx-swap="afterbegin"></div>
   ```

   The server's HTML fragment **always** renders rows as
   `<tr data-event-id="{{e.id}}">…</tr>` so the client can read ids from the DOM.
   `maxEventId()` lives in `app.js` (~3 lines) and scans the tbody for the highest
   `data-event-id`. Because `hx-include` always sends current filter values, the
   live-prepend automatically matches whatever filter the user has selected — no JS
   bookkeeping of URL parameters needed.

3. **Older rows**: `[ Load 50 older ]` button does
   `hx-get="/events.json?format=html&before_id={oldest_seen_id}&limit=50"` and swaps
   `beforeend` — appends rows.

### 5.4 Clip modal

```html
<dialog id="clip-modal" class="dialog">
  <header class="dialog-header">
    <h3 id="clip-title">Event …</h3>
    <button class="btn-ghost" onclick="document.getElementById('clip-modal').close()">✕</button>
  </header>
  <video id="clip-video" controls autoplay style="width:100%;max-height:70vh"></video>
  <footer class="dialog-footer">
    <span id="clip-meta" class="text-muted"></span>
    <a id="clip-download" class="btn btn-secondary" download>Download mp4</a>
  </footer>
</dialog>
```

Each `▶` link in the table is `<a href="#" onclick="openClip({id},'{ts}','{user}')">▶</a>`.
`openClip()` in `app.js` (~8 lines): sets `<video src>` to `/clips/{id}.mp4`, sets title
and download href, calls `dialog.showModal()`. Closing the dialog pauses + clears src
to free memory.

If `clip_path` is NULL on the event row, the `▶` is replaced with `—`.

---

## 6. Users page (`/users` — `users.html`)

### 6.1 Layout

Single full-width card with the table. Empty-state placeholder when the table is empty.

```
┌───────────────────────────────────────────────────────────────────────────┐
│ Users                                                  3 enrolled         │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ ID  Name     Created        Last seen      #encodings   QR active   │ │
│ ├─────────────────────────────────────────────────────────────────────┤ │
│ │ 1   alice    2026-05-01     2026-05-23     5            yes         │ │
│ │ 2   bob      2026-05-12     2026-05-23     3            yes         │ │
│ │ 3   carol    2026-05-20     —              5            yes         │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────────────┘
```

**Empty state:** when `users` is `[]`, render

```
No users enrolled.

Enroll one from the Pi:

  python -m smart_gate.cli enroll --name alice
```

inside the card.

### 6.2 No CRUD

Per Pi spec §15 ("Live face enroll from the Flask UI is out of scope"), this page is
read-only. The CLI is the source of truth for user mutation. The table is rendered
server-side on each GET; no HTMX polling (data changes rarely; user can refresh).

---

## 7. System page (`/system` — `system.html`)

### 7.1 Layout

```
┌───────────────────────────────────────────────────────────────────────────┐
│ System                                                                    │
│                                                                           │
│ ┌──────────┬──────────┬──────────┬──────────┐                             │
│ │ LINK     │  CAP     │  DET     │  DISK    │  ← four big status cards    │
│ │  ●up     │ 14.2 fps │ 9.1 fps  │ 4.2 GB   │                             │
│ │ rx 0.4s  │ frame    │ skipped  │ free of  │                             │
│ │  ago     │ 0.18s    │  32%     │  16 GB   │                             │
│ └──────────┴──────────┴──────────┴──────────┘                             │
│                                                                           │
│ Health JSON                                                ▼ collapse     │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ {  "uptime_s": 42301,                                                │ │
│ │    "link_alive": true,    "last_frame_ago_s": 0.18,                  │ │
│ │    "cap_fps": 14.2,       "det_fps": 9.1,                            │ │
│ │    "events_today": 37,    "disk_free_gb": 4.2,                       │ │
│ │    "threads_ok": true }                                              │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
│ Diagnostics                                                               │
│ [ Send ping ]  [ Send cmd:status ]    response → modal                    │
│                                                                           │
│ ESP32 log                              ●live   [Pause]  [Clear]           │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ 14:02:09  INFO  rfid       UID 0xABCDEF granted (alice)              │ │
│ │ 14:01:51  INFO  servo      open angle=90                             │ │
│ │ 14:01:50  WARN  audio      missing peripheral, beep skipped          │ │
│ │ 14:00:30  INFO  boot       firmware 0.3.1                            │ │
│ │ … (live, newest on top, capped at 500 lines)                         │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Status cards

Each card is fed from `/healthz?format=html&panel=systemcards` (polled every 2.5 s,
same fragment endpoint pattern as topbar). LINK card shows reconnect attempt count
when down ("retry in 5s, attempt 3"). DISK card shows red border if free < 200 MB
(matching the recorder skip threshold from Pi spec §3.4).

### 7.3 Health JSON

Initial render server-side from `healthz()` JSON, pretty-printed with `<pre><code>`.
Refresh button (no auto-poll — would defeat the point of seeing a stable snapshot).

### 7.4 Diagnostics

Two buttons; each `hx-post` to `/api/diag/ping` or `/api/diag/status`. Response JSON
appears in a small modal (reuses `<dialog>` styling) with timing ("ack in 47 ms") and
ESP32-side payload pretty-printed. If the request times out (link down) the modal
shows the error message.

### 7.5 ESP32 log (live)

The log list is the centerpiece of this page.

```html
<div class="log-toolbar">
  <span class="pill pill-ok" id="sse-status"><span class="dot dot-ok"></span> live</span>
  <button class="btn btn-ghost" id="log-pause">Pause</button>
  <button class="btn btn-ghost" id="log-clear">Clear</button>
</div>
<ol class="esp-log" id="esp-log"
    hx-get="/api/esp_log?limit=100&format=html"
    hx-trigger="load"
    hx-swap="innerHTML">
</ol>
```

`app.js` (~12 lines):
1. On `DOMContentLoaded`, after the initial HTML fragment loads, open
   `new EventSource('/api/esp_log/stream')`.
2. On `'log'` event: prepend `<li>` from the JSON; cap list at 500 children
   (`while (list.children.length > 500) list.lastChild.remove()`).
3. On `onerror`: set `#sse-status` to `pill-warn` "reconnecting…"; EventSource auto-
   reconnects; on next `onopen`, reset to `pill-ok` "live".
4. `Pause` toggles a boolean that short-circuits the prepend; `Clear` empties the list.

### 7.6 Why SSE here (and not HTMX poll)

| Concern | HTMX poll every 2s | SSE |
|---|---|---|
| Latency for fresh log | up to 2 s | < 50 ms typical |
| Bandwidth when idle | ~200 B per poll × 30/min | 0 (just `: ping` every 15 s) |
| Bandwidth when active | duplicated rows until client tracks ids | exact-once delivery |
| Backpressure | none — easy to overrun client | server queue per subscriber |
| Reconnect / replay | manual `after_id` bookkeeping | native via `Last-Event-ID` header |

SSE wins on every axis except dependency cost — and EventSource is a browser native, so
that cost is zero.

---

## 8. Backend additions

### 8.1 `link/esp_log_bus.py` (NEW, ~40 LOC)

```python
"""In-process pub/sub for ESP32 log events.

Single publisher (smart_gate.main._handle_esp_event), N subscribers (one per
open SSE connection). Each subscriber gets its own bounded queue; overflow
drops the OLDEST entry (so a slow consumer never blocks the publisher and
the producer never blocks the bus-consumer thread)."""
from __future__ import annotations
import collections
import threading
from typing import Any


class EspLogBus:
    """Pub/sub with bounded per-subscriber queues."""

    def __init__(self, queue_cap: int = 200) -> None:
        self._queue_cap = queue_cap
        self._subscribers: set[collections.deque] = set()
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)

    def subscribe(self) -> collections.deque:
        q: collections.deque = collections.deque(maxlen=self._queue_cap)
        with self._lock:
            self._subscribers.add(q)
        return q

    def unsubscribe(self, q: collections.deque) -> None:
        with self._lock:
            self._subscribers.discard(q)

    def publish(self, item: dict) -> None:
        with self._cond:
            for q in self._subscribers:
                q.append(item)            # drops oldest if full
            self._cond.notify_all()

    def wait_for_item(self, q: collections.deque,
                      timeout: float = 1.0) -> dict | None:
        with self._cond:
            if q:
                return q.popleft()
            self._cond.wait(timeout=timeout)
            return q.popleft() if q else None

    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subscribers)
```

### 8.2 `main.py` wiring

```python
from smart_gate.link.esp_log_bus import EspLogBus

# in main():
esp_log_bus = EspLogBus()

# pass into _consume_bus and _run_web:
threads = [
    ...
    threading.Thread(target=_consume_bus, name="bus-consumer",
                     args=(bus, db, matcher, uart, trig_queue, cfg, shutdown,
                           reload_event),
                     kwargs={"pending": pending, "esp_log_bus": esp_log_bus},
                     daemon=True),
    threading.Thread(target=_run_web, name="flask",
                     args=(cfg, db, hub, uart, data_dir, shutdown),
                     kwargs={"matcher": matcher, "overlay": overlay,
                             "reload_event": reload_event,
                             "esp_log_bus": esp_log_bus},
                     daemon=True),
    ...
]

# in _handle_esp_event, for v == "log":
def _handle_esp_event(evt, db, matcher, trig_queue, pending=None,
                      reload_event=None, esp_log_bus=None):
    if evt.v == "log":
        d = evt.data or {}
        log_id = db.insert_esp_log(d.get("lvl","info"), d.get("tag"),
                                   d.get("msg",""))
        if esp_log_bus is not None:
            esp_log_bus.publish({
                "id":  log_id,
                "ts":  d.get("ts") or _now_iso(),
                "lvl": d.get("lvl","info"),
                "tag": d.get("tag"),
                "msg": d.get("msg",""),
            })
        return
    # ... rest unchanged
```

`db.insert_esp_log()` is modified to `return cur.lastrowid`. No schema change.

### 8.3 `data/db.py` additions

```python
def insert_esp_log(self, lvl: str, tag: str | None, msg: str) -> int:
    conn = self.connect()
    cur = conn.execute("INSERT INTO esp_log(lvl, tag, msg) VALUES (?, ?, ?)",
                       (lvl, tag, msg))
    conn.commit()
    return cur.lastrowid                                  # NEW return

def recent_esp_log(self, limit: int = 100, after_id: int = 0) -> list[tuple]:
    conn = self.connect()
    return list(conn.execute("""
        SELECT id, ts, lvl, tag, msg FROM esp_log
        WHERE id > ?  ORDER BY id DESC  LIMIT ?
    """, (after_id, limit)))

def recent_events(self, limit: int = 50, after_id: int = 0,
                  before_id: int | None = None,
                  method: list[str] | None = None,
                  granted: int | None = None,
                  q: str | None = None,
                  since: str | None = None) -> list[tuple]:
    """Extended filter set. All filters optional; all combine with AND.

    `method` is a list of method-strings, OR'd. `q` is a case-insensitive
    LIKE on users.name. `since` is an ISO timestamp; events with ts >= since.
    `before_id` is for keyset pagination of older rows.
    """
    where = ["e.id > ?"]
    params: list = [after_id]
    if before_id is not None:
        where.append("e.id < ?"); params.append(before_id)
    if method:
        where.append("e.method IN (" + ",".join(["?"] * len(method)) + ")")
        params.extend(method)
    if granted is not None:
        where.append("e.granted = ?"); params.append(int(granted))
    if q:
        where.append("u.name LIKE ?"); params.append(f"%{q}%")
    if since:
        where.append("e.ts >= ?"); params.append(since)
    params.append(limit)
    conn = self.connect()
    return list(conn.execute(f"""
        SELECT e.id, e.ts, e.method, e.user_id, u.name, e.granted, e.detail, e.clip_path
        FROM events e LEFT JOIN users u ON u.id = e.user_id
        WHERE {' AND '.join(where)}
        ORDER BY e.id DESC LIMIT ?
    """, params))

def count_events_today(self) -> int:
    conn = self.connect()
    return conn.execute(
        "SELECT COUNT(*) FROM events WHERE ts >= datetime('now','start of day')"
    ).fetchone()[0]
```

Backward-compat: `recent_events(limit=50, after_id=0)` calls still work — all new
params are keyword-only and default to None.

### 8.4 `web/app.py` routes

| Route | Method | Behavior |
|---|---|---|
| `/` | GET | render `dashboard.html` |
| `/events` | GET | render `events.html`; pre-populate filter form from query string |
| `/users` | GET | render `users.html` |
| `/system` | GET | render `system.html`; pre-render initial healthz JSON |
| `/stream.mjpeg` | GET | unchanged |
| `/clips/<id>.mp4` | GET | unchanged |
| `/events.json` | GET | **extend**: accept `method` (repeated), `granted`, `q`, `period`, `before_id`, `format=html`; return JSON or HTML fragment of `<tr>` rows |
| `/healthz` | GET | **extend**: add `cap_fps, det_fps, events_today, disk_free_gb, last_grant{name,ts}`; if `format=html`, render one of `_partials/statusbar.html` / `banner.html` / dashboard quickstats / system cards based on `panel=` query |
| `/api/esp_log` | GET | HTML fragment (`format=html` default) or JSON; `limit`, `after_id` params |
| `/api/esp_log/stream` | GET | **NEW SSE** — see §8.5 |
| `/api/gate/open`, `/api/gate/close` | POST | unchanged behavior; on 503 the client toast surfaces |
| `/api/diag/ping` | POST | call `uart.send_cmd("ping", timeout=2)` with `time.monotonic()` bracket; return `{"ack_ms": int, "data": ...}` (ack_ms measured by route, not from firmware) or 503 with `{"error": "..."}` |
| `/api/diag/status` | POST | same pattern with `uart.send_cmd("status", timeout=2)` |

`create_app(...)` gains a keyword `esp_log_bus=None`. When None, `/api/esp_log/stream`
returns 503 (used by tests that don't construct the bus).

### 8.5 SSE handler

```python
@app.route("/api/esp_log/stream")
def esp_log_stream():
    if esp_log_bus is None:
        return jsonify({"error":"esp_log_bus not configured"}), 503

    last_id = int(request.headers.get("Last-Event-ID", "0") or "0")

    def gen():
        # Replay any missed rows since last_id (max 200 to bound payload).
        if last_id > 0:
            backlog = db.recent_esp_log(limit=200, after_id=last_id)
            for row in reversed(backlog):                   # oldest first
                yield _sse_format(row_to_dict(row))

        q = esp_log_bus.subscribe()
        try:
            last_ping = time.monotonic()
            while True:
                item = esp_log_bus.wait_for_item(q, timeout=1.0)
                if item is not None:
                    yield _sse_format(item)
                # Keepalive every ~15s so proxies/load-balancers don't drop us.
                if time.monotonic() - last_ping > 15:
                    yield ": ping\n\n"
                    last_ping = time.monotonic()
        except GeneratorExit:
            pass
        finally:
            esp_log_bus.unsubscribe(q)

    return Response(gen(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache",
                             "X-Accel-Buffering": "no"})

def _sse_format(item: dict) -> str:
    return (f"id: {item['id']}\n"
            f"event: log\n"
            f"data: {json.dumps(item, separators=(',',':'))}\n\n")
```

Werkzeug threaded server holds one thread per SSE connection — acceptable for ≤ 4
concurrent admin tabs (the realistic upper bound). No keepalive timeout is set; the
generator's own `: ping` line keeps the connection from being mid-box-dropped.

---

## 9. Error handling & resilience

| Failure | Surface |
|---|---|
| UART link down | top-bar pill turns amber + "LINK", `link-banner` fragment populated; gate buttons still POST but get 503 → toast "Gate command failed (link down)" |
| Camera stale (last_frame_ago > 5s) | Quick-stat "frame age" turns red; CSS overlay "Camera offline" on the stream image (CSS-only, fires off `<img>` `onerror`) |
| SSE disconnect | `#sse-status` pill turns amber "reconnecting…"; EventSource auto-reconnects; on reopen the `Last-Event-ID` header lets server replay missed rows |
| /healthz fragment HTTP error | HTMX leaves last fragment in place; one log line on browser console; no toast (avoids noise during transient errors) |
| /events.json HTTP error | Same as above; the polling div continues, hides errors |
| Empty events / users / log | Each table/list renders its own empty-state message inside the card |
| Disk free < 200 MB | DISK card on /system shows red border + "low" pill |
| Diag ping/status timeout | Modal shows red banner "no ack in 2.0s — link may be down" |
| Multiple SSE tabs | Each tab gets its own bus subscriber + queue; no shared state issues |

---

## 10. JS file (`static/app.js`, complete, ~50 LOC)

```javascript
// Smart Gate — admin UI sprinkles.
(function () {
  // ----- Toast on HTMX request results -----
  const toastWrap = document.createElement('div');
  toastWrap.className = 'toast-wrap';
  document.body.appendChild(toastWrap);

  function toast(msg, kind) {
    const el = document.createElement('div');
    el.className = `toast toast-${kind || 'info'}`;
    el.textContent = msg;
    toastWrap.appendChild(el);
    requestAnimationFrame(() => el.classList.add('toast-show'));
    setTimeout(() => {
      el.classList.remove('toast-show');
      setTimeout(() => el.remove(), 250);
    }, 3500);
  }

  document.body.addEventListener('htmx:afterRequest', (e) => {
    const tgt = e.detail.elt;
    const ok  = e.detail.successful;
    const msg = tgt.dataset[ok ? 'toastOk' : 'toastErr'];
    if (msg) toast(msg, ok ? 'ok' : 'danger');
  });

  // ----- Clip modal -----
  window.openClip = function (id, ts, user) {
    const dlg = document.getElementById('clip-modal'); if (!dlg) return;
    document.getElementById('clip-title').textContent = `Event #${id} · ${ts} · ${user || '—'}`;
    const v = document.getElementById('clip-video');
    v.src = `/clips/${id}.mp4`;
    const dl = document.getElementById('clip-download');
    dl.href = `/clips/${id}.mp4`; dl.download = `event-${id}.mp4`;
    dlg.showModal();
    dlg.addEventListener('close', () => { v.pause(); v.removeAttribute('src'); v.load(); }, { once: true });
  };

  // ----- SSE for ESP32 log (only on /system) -----
  const logList = document.getElementById('esp-log');
  if (logList) {
    let paused = false, capacity = 500;
    const status = document.getElementById('sse-status');
    document.getElementById('log-pause')?.addEventListener('click', (e) => {
      paused = !paused; e.target.textContent = paused ? 'Resume' : 'Pause';
    });
    document.getElementById('log-clear')?.addEventListener('click', () => {
      logList.innerHTML = '';
    });
    const es = new EventSource('/api/esp_log/stream');
    es.addEventListener('log', (e) => {
      if (paused) return;
      const r = JSON.parse(e.data);
      const li = document.createElement('li');
      li.dataset.lvl = r.lvl || 'info';
      li.innerHTML =
        `<time>${(r.ts||'').slice(11,19)}</time>` +
        `<span class="pill pill-${(r.lvl||'info').toLowerCase()}">${r.lvl||'info'}</span>` +
        `<span class="tag">${r.tag || ''}</span>` +
        `<span class="msg">${r.msg.replace(/[<>&]/g, c => ({'<':'&lt;','>':'&gt;','&':'&amp;'}[c]))}</span>`;
      logList.insertBefore(li, logList.firstChild);
      while (logList.children.length > capacity) logList.lastChild.remove();
    });
    es.onopen  = () => { if (status) { status.className = 'pill pill-ok';
                                       status.innerHTML = '<span class="dot dot-ok"></span> live'; } };
    es.onerror = () => { if (status) { status.className = 'pill pill-warn';
                                       status.innerHTML = '<span class="dot dot-warn"></span> reconnecting…'; } };
  }

  // ----- /events live-prepend helper: latest seen id (called via hx-vals js:) -----
  window.maxEventId = function () {
    let m = 0;
    document.querySelectorAll('#events-tbody tr[data-event-id]').forEach((tr) => {
      m = Math.max(m, parseInt(tr.dataset.eventId, 10) || 0);
    });
    return m;
  };
})();
```

---

## 11. Tests

### 11.1 Unit additions

`tests/unit/test_db.py` — extend:
- `recent_events(method=['face','qr'])` returns only those methods.
- `recent_events(granted=0)` returns only denials.
- `recent_events(q='ali')` matches partial user name.
- `recent_events(before_id=N)` returns rows with id < N (keyset pagination).
- `recent_esp_log(limit=10)` ordering: DESC by id.
- `recent_esp_log(after_id=N)` returns only newer rows.
- `count_events_today()` counts only today's rows (mock `datetime('now')`).
- `insert_esp_log()` now returns the inserted id (existing tests still pass).

`tests/unit/test_esp_log_bus.py` — new:
- subscribe → publish → wait_for_item returns the item.
- two subscribers both receive the same item.
- queue overflow drops oldest (publish 201 items, queue_cap=200, oldest dropped).
- unsubscribe removes from set; subscriber_count reflects.
- wait_for_item with timeout returns None on empty.

### 11.2 Integration additions

`tests/integration/test_web.py` — new:

```python
def test_dashboard_renders(client):       # GET / 200, contains "Live preview"
def test_events_renders(client):          # GET /events 200, contains filter pills
def test_users_renders_empty(client):     # GET /users 200, contains "No users enrolled"
def test_users_renders_with_data(client): # seed one user, contains name
def test_system_renders(client):          # GET /system 200, contains "ESP32 log"
def test_events_filter_method(client):    # seed mix; GET /events.json?method=face → only face
def test_events_filter_granted(client):   # GET /events.json?granted=0 → only denials
def test_events_filter_q(client):         # GET /events.json?q=ali → only matching user
def test_events_html_fragment(client):    # ?format=html → returns <tr> rows, not full HTML
def test_healthz_panel_statusbar(client): # ?format=html&panel=statusbar → expected pills
def test_clip_404_when_null(client):      # event without clip → 404
def test_gate_open_503_when_link_down(client):  # fake uart raising LinkDown → 503
def test_esp_log_stream_round_trip(client, esp_log_bus):
    # Open SSE in a thread, publish via bus, assert event arrives within 1s.
def test_esp_log_stream_replay(client, db):
    # Seed 5 rows, request with Last-Event-ID=3, assert 2 newer rows are replayed.
def test_esp_log_stream_unsubscribe_on_disconnect(client, esp_log_bus):
    # Open + close client; assert bus.subscriber_count() returns to 0.
```

Conftest already provides `db` and `client`; add `esp_log_bus` fixture.

### 11.3 Manual smoke test (in README)

After branch merges, with daemon running and ESP32 connected:
1. Open `http://<pi>:8080/` — stream visible, FPS pills update, click Open/Close → toast.
2. Trigger a face match — row appears at top of Recent events within 2 s.
3. Open `/events` — filter to `denied` → only denials show; click `▶` on a clip → modal plays.
4. Open `/system` — Diag → Send ping → modal "ack in <X> ms"; tail of ESP32 log scrolls live.
5. Unplug USB to ESP32 — within 5 s: top-bar LINK pill amber, banner appears, gate buttons → 503 toast, SSE pill "reconnecting…". Replug — banner disappears, SSE pill goes live, missed log lines replayed.

---

## 12. Performance & resource

- **JS payload:** htmx.min.js 14 KB + app.js ~3 KB = ~17 KB gzipped — minimal.
- **CSS payload:** app.css ~6 KB minified ~3 KB gzipped vs. Pico 30 KB — net win.
- **Memory:** EspLogBus per-subscriber queue cap 200 items × ~200 B each = 40 KB per tab.
- **CPU:** SSE generator wakes every 1 s on `wait_for_item` timeout — negligible at idle. Under burst (e.g., 50 log lines/sec) the per-subscriber memcpy is microseconds.
- **DB:** all new queries are O(log N) keyset reads; no full-table scans on the hot path. Filter LIKE on `users.name` is O(N_users) ≤ ~200.
- **Threads:** Werkzeug threaded server already spawns one thread per request — SSE inherits this. No new persistent threads.

---

## 13. Out of scope (deferred)

- Authentication / login (LAN-only assumption, Pi spec §15).
- User CRUD from web (CLI only, Pi spec §9 / §15).
- Live face enroll from web (Pi spec §15).
- Real-time charts / sparklines for FPS.
- Mobile / touch responsive layout (desktop-only, single user).
- WebSocket (SSE covers our one-way streaming need).
- Dark-mode toggle (foundation is laid via CSS variables; toggle itself is deferred).
- i18n.
- Live video clip preview thumbnails in the events table (server-side thumb generation is not in scope).
- Pagination beyond keyset "load older" (no jump-to-page).
- Export events as CSV / JSON.
- Push notifications.

---

## 14. Open risks

1. **HTMX `swap=outerHTML` on the toolbar fragment** loses ephemeral state (e.g., open dropdowns) when it refreshes. Mitigation: the toolbar contains only stateless pills; no menus live in there.
2. **SSE behind proxies/reverse-proxies.** If a future deployment puts nginx in front of Flask, the `X-Accel-Buffering: no` header is included to disable nginx response buffering, but other proxies may strip it. Current deployment is direct Werkzeug — fine.
3. **Werkzeug's threaded server has no max-connections limit** — an attacker on the LAN could exhaust threads by opening many `/api/esp_log/stream` connections. Mitigation: LAN-only deployment per architecture decision; documented in README. If a hostile environment ever applies, switch to gunicorn (out of scope for v1).
4. **`Last-Event-ID` reconnect backlog** is capped at 200 rows to bound payload; if the client was disconnected for hours, older lines are skipped. The full table is still queryable via `/api/esp_log?after_id=N` if needed.
5. **`<dialog>` element** is supported in all evergreen browsers as of 2024 but does not work in old Safari (< 15.4). Demo target is current Chrome/Firefox/Edge on desktop — acceptable.

---

*End of design doc.*

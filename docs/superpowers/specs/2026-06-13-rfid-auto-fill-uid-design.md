# RFID Auto-fill UID in Add-user Modal — Design Spec

**Date:** 2026-06-13
**Branch:** `feat/safety-fixes`
**Status:** Approved

## Problem

The Add-user modal's RFID mode requires the admin to type UID hex manually
(`<input id="au-rfid-uid">`). The admin has to:

1. Open the modal in RFID mode.
2. Quẹt thẻ mới ở đầu đọc.
3. Open the live-log toast or `/api/esp_log` page, find the line
   `[warn] rfid: denied uid=AB12CD34 name=(unknown)`, copy the hex.
4. Paste it into the input.
5. Submit.

Steps 3-4 are friction. The UID is already streaming through the dashboard
SSE channel — auto-filling the input the moment a new card is swiped would
collapse the workflow to: open modal → swipe → submit.

## Goals

1. While the Add-user modal is open in RFID mode, intercept the next swipe
   event from `/api/esp_log/stream` whose `msg` contains a `uid=...` token
   and write the captured hex into `#au-rfid-uid`.
2. Visual confirmation — brief border flash on the input — so the admin
   knows the value came from a swipe vs. their own typing.
3. Subsequent swipes overwrite the field (admin can swipe a different card
   before clicking submit).
4. When the modal closes or the admin switches to Face mode, stop listening.

Non-goals:
- Backend changes (no new SSE topic, no new event verb).
- Suppressing the existing audit-log `[warn] rfid denied …` entry when the
  modal is open (rare, low-cost noise; can revisit later).
- Auto-submit on swipe (admin must still click "Tạo + Bind" — gives a chance
  to reject a wrong card).
- Auto-fill from `granted on ESP but unknown to Pi` edge case (different log
  format, hits only when DB and ESP allowlist drift apart — rare and the
  fallback path of manual typing is fine).

## Architecture

Pure client-side change. The Add-user modal IIFE in `dashboard.html` already
exists; this work adds an SSE listener scoped to the modal's open lifetime.

### Data flow (already in place — no changes)

```
ESP swipe → UART evt:rfid (denied) → main.py:506 _audit(…"denied uid=AB12CD34 name=(unknown)"…)
         → esp_log_bus.publish({lvl:"warn", tag:"rfid", msg:"…", direction:"←", …})
         → SSE /api/esp_log/stream → browser EventSource
```

### What we add (client only)

In the existing modal IIFE (`dashboard.html` around the `applyMode()` block):

```js
const UID_RE = /uid=([0-9A-Fa-f]{4,24})\b/;
let rfidEs = null;   // EventSource — only alive while modal+RFID mode

function startRfidListen() {
  if (rfidEs) return;
  rfidEs = new EventSource('/api/esp_log/stream');
  rfidEs.addEventListener('log', function (ev) {
    let item;
    try { item = JSON.parse(ev.data); } catch (e) { return; }
    if (item.tag !== 'rfid') return;
    const m = UID_RE.exec(item.msg || '');
    if (!m) return;
    uidInput.value = m[1].toUpperCase();
    uidInput.classList.add('au-rfid-flash');
    setTimeout(function () {
      uidInput.classList.remove('au-rfid-flash');
    }, 800);
  });
}

function stopRfidListen() {
  if (!rfidEs) return;
  rfidEs.close();
  rfidEs = null;
}
```

Wire to lifecycle:
- `applyMode()` — when switching INTO rfid mode, call `startRfidListen()`;
  when switching OUT of rfid mode, call `stopRfidListen()`.
- `cancelBtn` click → `stopRfidListen()`.
- `modal.addEventListener('close', stopRfidListen)` — fires on `<dialog>`
  close from ESC key or backdrop click or programmatic `.close()`.
- `form.addEventListener('submit', …)` after the await: `stopRfidListen()`
  on the same form-submit handler's `finally` branch.

Additional CSS (append to the existing inline `<style>` block in
`dashboard.html`):

```css
@keyframes au-rfid-flash-kf {
  0%   { box-shadow: 0 0 0 2px #10b981; }
  100% { box-shadow: 0 0 0 0 transparent; }
}
.au-rfid-flash {
  animation: au-rfid-flash-kf 800ms ease-out;
}
```

(Green `#10b981` matches existing `--ok` palette.)

### Why a fresh EventSource per modal open

The existing toast IIFE already holds one `EventSource('/api/esp_log/stream')`.
Two co-existing EventSources to the same URL is fine for Werkzeug dev server
(thread-per-client) and for the production worker count — current dashboard
already opens one. Each gets its own copy of every event; no shared filtering
needed. Cleaner than sharing a global pub-sub.

If a second EventSource per page proves expensive (it shouldn't — SSE is
cheap text streaming), a future refactor can hoist the EventSource into a
small JS module that maintains a callback list. Out of scope here.

## Lifecycle state machine

```
┌──────────┐   open modal + mode=rfid    ┌────────────┐
│  CLOSED  │ ──────────────────────────► │ LISTENING  │
│ (no ES)  │                             │  (ES open) │
└──────────┘                             └────────────┘
     ▲                                         │
     │ stop on:                                │ on rfid log msg with uid=…:
     │  - cancel click                         │   uidInput.value = uid
     │  - modal close event                    │   flash class for 800ms
     │  - mode switch → face                   │
     │  - submit finally branch                │
     └─────────────────────────────────────────┘
```

The `if (rfidEs) return` guard at the top of `startRfidListen()` makes
multiple calls idempotent.

## Testing

### Manual

1. Open the dashboard. Click `+ Tạo user mới` → modal opens (Face mode by
   default). DevTools Network tab: no new SSE to `/api/esp_log/stream`
   from the modal (only the toast IIFE's existing one).
2. Click the RFID radio. DevTools Network: a SECOND EventSource opens.
3. Quẹt thẻ mới ở đầu đọc. Within 1 sec the input should contain the UID
   hex (uppercase, no separators), with a brief green border flash.
4. Quẹt thẻ thứ hai. Input updates to the new UID.
5. Click `Hủy`. Network tab: the second EventSource closes.
6. Re-open modal → switch directly to RFID → quẹt → fill OK.
7. Open modal in RFID mode → swipe → click submit. After the POST
   completes (success or fail), Network tab: the second EventSource closes.
8. Open modal in Face mode → swipe nearby → input UID should NOT auto-fill
   (mode-scoped listener was never started).

### Negative

- Quẹt thẻ ĐÃ enrolled. ESP returns `granted` → Pi audit message is
  `granted on ESP but unknown to Pi: name=X` or no audit at all if Pi
  has the user. The msg does NOT match `uid=...` regex (it has `name=`
  but no `uid=` token in granted path). Input must NOT auto-fill —
  verify the regex truly fails on those.
- Mid-typing collision: admin types a UID manually, then accidentally
  triggers a swipe. Auto-fill overwrites. ACCEPTED — admin can re-type.
  (This is the simplest behavior; the alternative — locking after
  manual edit — adds state and isn't worth the complexity.)

### Unit (optional, light)

Pure-JS regex test — not yet covered by the project's test harness; the
behavior is small enough to verify by manual smoke alone. Skip.

## Error handling

- EventSource throws on `new EventSource(…)` (extremely rare; only if URL
  is malformed): catch silently. Auto-fill simply doesn't work, admin types
  manually. Do not show an error toast — it would be noise.
- SSE disconnect mid-modal (Pi reboots, network blip): EventSource auto-
  reconnects per spec. No special handling.
- Multiple consecutive swipes within 800ms: each clears + re-adds the
  flash class. Last UID wins. Animation may abort partway; that's fine.

## Files touched

| Path                                              | Action | LOC |
|---------------------------------------------------|--------|-----|
| `smart_gate/web/templates/dashboard.html`         | Modify | ~35 |

(All changes inline in the existing `<script>` IIFE and `<style>` block;
no new files.)

## Rollout

1. Implement + manual local smoke (open page, watch DevTools).
2. Commit.
3. scp dashboard.html to `/opt/smart-gate/...templates/`, sudo chown, restart.
4. Hard-refresh browser, run manual verification list above.

## Open questions

None. Design intentionally simple: one EventSource per modal open, regex
parse, scoped lifetime.

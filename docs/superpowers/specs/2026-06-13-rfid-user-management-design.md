# RFID User-Management Overhaul — Design Spec

**Date:** 2026-06-13
**Branch:** `feat/safety-fixes`
**Status:** Approved
**Supersedes:** `2026-06-13-rfid-auto-fill-uid-design.md` (auto-fill folded in as
Feature 1 below; prior spec/plan kept in git history but no longer authoritative)

## Problem

Four related gaps in current RFID-side user management:

1. **Manual UID entry.** Admin must read UID off live-log toast and paste
   into the Add-user modal. The data is already streaming through SSE.

2. **Add card cannot target an existing user.** Dashboard's "+ Tạo user mới"
   modal in RFID mode always creates a fresh `user_NNN`. If user_007 was
   created via Face and admin now wants to give them a card, the modal
   creates `user_008` instead — two separate users with split auth methods,
   neither can open the gate via both.

3. **No UI to remove a card.** Backend route `DELETE /api/users/<name>/rfid/<uid>`
   exists (`app.py:379`), but the `/users` page only has Add-RFID form, no
   visible list of bound UIDs and no remove button. The firmware verb
   `list_uids` already returns `[{uid, name}, ...]` (`allowlist.cpp:128`)
   so the data path is in place.

4. **Delete-user does not cascade UID removal.** `DELETE /api/users/<name>`
   (`app.py:296`) cascades face_encodings + qr_tokens via SQLite FK and
   removes the QR PNG, but does NOT call `cmd:remove_uid`. The user's UIDs
   stay in ESP NVS allowlist forever. Swiping a deleted user's card still
   opens the gate; ESP grants, Pi logs "granted on ESP but unknown to Pi"
   (`main.py:515`) silently. This is a real security gap.

## Goals

One coherent UI sweep that closes all four gaps. Single feature branch,
single set of commits, easy to review as a unit.

### Feature 1 — Auto-fill UID

While the Add-user modal is in RFID mode, listen to `/api/esp_log/stream`,
extract `uid=([0-9A-Fa-f]{4,24})` from `rfid`-tagged messages, populate the
UID input with brief green-border flash.

### Feature 2 — Target picker in modal RFID mode

Add a radio above the UID input:

- **Tạo user mới** (default) — current behavior: `POST /api/enroll
  {face_capture:false}` → `POST /api/users/<new>/rfid {uid}`.
- **Bind vào user có sẵn** — new behavior: dropdown populated from
  `GET /api/users.json` (already exists). Submit: only `POST
  /api/users/<existing>/rfid {uid}`. No enroll, no new SQLite row.

### Feature 3 — List + remove UIDs on `/users` page

Each user row gains a UIDs sub-list rendered from a new endpoint
`GET /api/users/<name>/rfid.json` → returns `{"uids": ["AB12CD34", ...]}`
filtered server-side. Each item gets an `×` button that fires
`DELETE /api/users/<name>/rfid/<uid>` (existing route) and removes the
chip on success.

The new GET endpoint internally:
1. `uart.send_cmd("list_uids", {}, timeout=2.0)`
2. Parse ack data `[{uid, name}, ...]`
3. Filter to entries where `name == requested_name`
4. Return `{"uids": [list of uid strings]}`

### Feature 4 — Cascade UID removal on delete-user

`DELETE /api/users/<name>` is extended:
1. Before SQLite delete: list UIDs bound to this name (reuse the same
   internal call from Feature 3).
2. For each UID: `uart.send_cmd("remove_uid", {"uid": …}, timeout=2.0)`.
   Best-effort; failures are logged + audited, do NOT abort the SQLite
   delete (admin can re-run if a UID survives).
3. Existing cascade flow (face_encodings + qr_tokens + QR PNG + matcher
   reload) continues unchanged.

If UART is down (LinkDown), skip the ESP cascade entirely and log a WARN
audit entry telling the admin to flush ESP allowlist manually once the
link is back. Don't block user deletion on UART availability — the SQLite
side is the primary identity record.

## Architecture

### Component changes

```
smart_gate/web/app.py
  +  _list_uids_for_user(uart, name) -> list[str]    # shared helper
  +  GET /api/users/<name>/rfid.json                 # Feature 3 read endpoint
  ~  DELETE /api/users/<name>                        # Feature 4 cascade
  (existing POST /api/users/<name>/rfid + DELETE /api/users/<name>/rfid/<uid>
   stay as-is — Features 2 + 3 client just call them)

smart_gate/web/templates/dashboard.html
  ~  Add-user modal IIFE:
     + Feature 1 SSE listener (mode-scoped EventSource)
     + Feature 2 target radio + user dropdown
     + Feature 2 submit logic split (existing vs new user)

smart_gate/web/templates/users.html
  ~  Per-row template:
     + UIDs chip list (server-rendered seed via Jinja from list_uids)
     + Per-chip × delete button → fetch DELETE → remove chip on success

smart_gate/web/static/app.css
  +  .au-rfid-flash keyframe (Feature 1)
  +  .uid-chip styling (Feature 3)
```

No firmware changes. No DB migration. No new endpoints beyond the one read
helper.

### Data flow (delete user, Feature 4)

```
admin clicks "Xóa user X"
  ↓
Pi: list_uids cmd → ESP → ack {uids: [...]} → filter by name=X → ["uid1","uid2"]
  ↓
for each uid: remove_uid cmd → ESP → ack ok      (best-effort)
  ↓
SQLite DELETE FROM users WHERE name=X   (cascade encodings + qr_tokens)
  ↓
qr_path.unlink()
  ↓
matcher.reload()
  ↓
200 {"ok":true, "removed_uids":2}
```

If `list_uids` times out: log + audit warn, skip remove_uid loop, continue
with SQLite delete. Same if individual `remove_uid` fails: log per-UID
failure, continue with the rest. Return body includes `failed_uids: [...]`
so the UI can warn the admin.

### Decision: filter UIDs Pi-side, not firmware-side

`cmd:list_uids` returns the full table. Filtering by name happens in Python
(`_list_uids_for_user`). Alternative would be a new firmware verb
`list_uids_by_name`, but:
- ESP allowlist holds ~50 entries max; list payload < 2 KB.
- Pi-side filter avoids a firmware respin.
- Same helper is shared between Feature 3 (list) and Feature 4 (cascade).

### Decision: dropdown vs. type-ahead in Feature 2

Plain `<select>` dropdown. User count expected < 50; alphabetical sort is
enough. Type-ahead adds JS complexity for a 1-screen-of-list problem.

### Decision: order of operations in Feature 4

Best-effort ESP cascade BEFORE SQLite delete. Rationale: if SQLite delete
succeeds but ESP cascade fails, we've lost the link between name → UIDs (no
more rows to look up). Doing ESP first means even a partial failure leaves
the next admin able to retry by deleting again (re-run will find SQLite row
gone but use the user-name from the request to retry remove_uid only on
surviving entries — though in practice this isn't built; admin manually
intervenes via `/api/users/<old_name>/rfid/<uid>` if they remember the UID).

A more rigorous approach is two-phase commit with rollback on partial
failure, but that's overkill for an admin-only delete operation. The
"removed_uids + failed_uids" response gives admin enough signal.

## Testing

### Unit (Python)

`tests/web/test_user_rfid_management.py` (new):

| Case                                          | Setup                                | Assertion                                        |
|-----------------------------------------------|--------------------------------------|--------------------------------------------------|
| `_list_uids_for_user` filters by name         | mock uart, ack `[{uid:A,name:X},{uid:B,name:Y}]`, ask for X | returns `["A"]`                                  |
| `_list_uids_for_user` LinkDown                | mock uart raises LinkDown            | returns `[]` (caller treats as "no ESP data")    |
| `_list_uids_for_user` malformed ack           | mock uart returns `{"data":{}}`      | returns `[]`                                     |
| `GET /api/users/<name>/rfid.json`             | mock uart returns 2 uids for name    | 200, body `{"uids":["A","B"]}`                   |
| `DELETE /api/users/<name>` cascades UIDs      | mock uart records remove_uid calls   | both calls present, response `removed_uids:2`    |
| `DELETE /api/users/<name>` UART down          | mock uart raises LinkDown            | SQLite delete still succeeds, body `removed_uids:0, failed_uids:[]`, audit warn emitted |
| `DELETE /api/users/<name>` partial failure    | mock uart raises on uid B            | response `removed_uids:1, failed_uids:["B"]`, SQLite delete still succeeds |

### Manual

**Feature 1 (auto-fill):** open modal → RFID mode → swipe new card → UID
appears in input with green flash within 1 s.

**Feature 2 (target picker):**
- Switch radio to "Bind vào user có sẵn" → dropdown populates from existing
  users. Pick one → submit with UID → no new SQLite row created (verify via
  `/users` count unchanged + the picked user now has 1 UID in `/users` page).
- Switch radio back to "Tạo user mới" → submit → new `user_NNN` row + 1 UID.

**Feature 3 (list + remove):** open `/users` page → each user row shows
their UID chips (or "no cards" if empty). Click × on a chip → toast
"Removed uid=…" → chip disappears. Refresh page → chip stays gone.

**Feature 4 (cascade):**
1. Create user_Z, bind 2 UIDs (use auto-fill from Feature 1).
2. Click "Xóa user_Z" on `/users` page.
3. Confirm. Toast: "Xóa user_Z (2 UIDs removed)".
4. Swipe one of the previously-bound cards → ESP denies (no longer in
   allowlist). No "granted on ESP but unknown to Pi" log line.

**Feature 4 negative (UART down):**
1. Power off ESP (or unplug USB-C).
2. Click "Xóa user_Z" → SQLite delete succeeds → audit warn line
   visible in live log: "user_Z deleted on Pi; ESP allowlist not flushed
   (link down)".
3. Power ESP back on. The old UIDs are still in NVS — admin must manually
   `curl -X DELETE` or re-add then re-delete. Acceptable for this rare
   path; we log it loudly.

## Error handling

| Condition                                   | Behavior                                                   |
|---------------------------------------------|------------------------------------------------------------|
| `list_uids` UART timeout (Feature 3 GET)    | 503 + body `{"error":"esp link"}` — UI shows "—" instead of chip list |
| `list_uids` UART timeout (Feature 4)        | log + audit warn; skip ESP cascade; SQLite delete proceeds |
| `remove_uid` UART timeout per-UID (Feat 4)  | log per-UID; collect in `failed_uids`; continue            |
| Empty allowlist                              | empty chip list; "no cards" placeholder text               |
| User picks own deleted user in Feature 2    | submit fails with backend's existing 404 "user not found"  |
| Feature 1 swipe arrives mid-typing          | input overwritten with last UID — accepted UX trade-off    |
| Multiple modals open in different tabs      | each tab has its own EventSource; independent              |

## Files touched

| Path                                                    | Action | LOC |
|---------------------------------------------------------|--------|-----|
| `smart_gate/web/app.py`                                 | Modify | ~80 |
| `smart_gate/web/templates/dashboard.html`               | Modify | ~70 |
| `smart_gate/web/templates/users.html`                   | Modify | ~50 |
| `smart_gate/web/static/app.css`                         | Modify | ~25 |
| `tests/web/test_user_rfid_management.py`                | Create | ~150 |

Total ≈ 375 LOC (incl. tests). Single coherent diff, single PR worth of work.

## Rollout

1. Implement + unit tests (Tasks 1-5 below) all on local.
2. `pytest tests/web/` green.
3. Local smoke: `node --check` extracted dashboard.html `<script>`.
4. Commit each task separately.
5. scp 4 files + restart `smart-gate.service` on Pi (`/opt/smart-gate/...`).
6. Manual verification list above.

## Open questions

- **Cascade in Feature 4: best-effort vs. all-or-nothing?** Chose best-effort
  with structured response. If feedback says admin keeps getting confused
  state, we'll add a confirm-retry loop later — but YAGNI for now.
- **Dropdown content in Feature 2: include deleted/disabled users?** No, only
  users present in SQLite. `/api/users.json` already returns the right set.
- **Should Feature 1 keep listening across mode switches?** No — listener is
  strictly RFID-mode-scoped to avoid background SSE traffic when admin isn't
  enrolling.

# RFID User-Management Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Close four UX/security gaps around RFID user management in one coherent sweep — auto-fill UID, bind-to-existing-user in modal, list+remove UIDs per user, and cascade UID removal on user delete.

**Architecture:** All four features go through the existing UART verbs (`list_uids`, `add_uid`, `remove_uid`); no firmware changes. New shared helper `_list_uids_for_user(uart, name)` powers both the per-user UID list endpoint and the delete-user cascade. Dashboard modal grows a radio + dropdown; `/users` page grows a chip list with × buttons. Each task is independently committable.

**Tech Stack:** Python 3.13 / Flask / Jinja2 / vanilla JS / pytest with unittest.mock.

---

## Task 1: Shared `_list_uids_for_user` helper + unit tests (TDD)

**Files:**
- Modify: `smart_gate/web/app.py` (add helper at module scope, near `_emit_audit`)
- Create: `tests/web/test_user_rfid_management.py`

- [ ] **Step 1: Write failing tests**

Create `tests/web/test_user_rfid_management.py`:

```python
"""Tests for /api/users/<name>/rfid management — helper + endpoints."""
from __future__ import annotations
from unittest.mock import Mock

import pytest

from smart_gate.link.uart_client import LinkDown, LinkTimeout


def _ack(uids):
    """Build a fake ack object matching what UartClient.send_cmd returns
    for the `list_uids` verb: a dict whose 'data' carries the uid list."""
    return {"data": {"uids": uids}}


def test_list_uids_for_user_filters_by_name():
    from smart_gate.web.app import _list_uids_for_user
    uart = Mock()
    uart.send_cmd.return_value = _ack([
        {"uid": "AAAA1111", "name": "alice"},
        {"uid": "BBBB2222", "name": "bob"},
        {"uid": "CCCC3333", "name": "alice"},
    ])
    assert _list_uids_for_user(uart, "alice") == ["AAAA1111", "CCCC3333"]


def test_list_uids_for_user_returns_empty_on_link_down():
    from smart_gate.web.app import _list_uids_for_user
    uart = Mock()
    uart.send_cmd.side_effect = LinkDown("no esp")
    assert _list_uids_for_user(uart, "alice") == []


def test_list_uids_for_user_returns_empty_on_timeout():
    from smart_gate.web.app import _list_uids_for_user
    uart = Mock()
    uart.send_cmd.side_effect = LinkTimeout("slow esp")
    assert _list_uids_for_user(uart, "alice") == []


def test_list_uids_for_user_returns_empty_on_malformed_ack():
    from smart_gate.web.app import _list_uids_for_user
    uart = Mock()
    uart.send_cmd.return_value = {"data": {}}
    assert _list_uids_for_user(uart, "alice") == []


def test_list_uids_for_user_none_uart():
    from smart_gate.web.app import _list_uids_for_user
    assert _list_uids_for_user(None, "alice") == []
```

- [ ] **Step 2: Run tests; expect ImportError**

Run: `cd /home/nguyenvd/workspace/smart_gate && python -m pytest tests/web/test_user_rfid_management.py -v`
Expected: `cannot import name '_list_uids_for_user' from 'smart_gate.web.app'`.

- [ ] **Step 3: Implement helper in `app.py`**

In `smart_gate/web/app.py`, near `_emit_audit` (around line 59), add:

```python
def _list_uids_for_user(uart, name: str) -> list[str]:
    """Return UIDs in the ESP allowlist bound to `name`.

    Single call to `cmd:list_uids` returning [{uid, name}, ...]; filter
    Python-side. LinkDown/LinkTimeout/malformed payloads all return [],
    so callers can treat "no ESP data" as "no UIDs" without bespoke
    error handling at each call site.
    """
    if uart is None:
        return []
    try:
        ack = uart.send_cmd("list_uids", {}, timeout=2.0)
    except (LinkDown, LinkTimeout):
        return []
    except Exception:
        log.exception("list_uids: unexpected error")
        return []
    data = ack.get("data") if isinstance(ack, dict) else None
    if not isinstance(data, dict):
        return []
    entries = data.get("uids")
    if not isinstance(entries, list):
        return []
    return [e["uid"] for e in entries
            if isinstance(e, dict) and e.get("name") == name
            and isinstance(e.get("uid"), str)]
```

- [ ] **Step 4: Tests pass**

Run: `cd /home/nguyenvd/workspace/smart_gate && python -m pytest tests/web/test_user_rfid_management.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add smart_gate/web/app.py tests/web/test_user_rfid_management.py
git commit -m "feat(web): _list_uids_for_user helper — Pi-side filter of cmd:list_uids

Single shared call site for both the per-user UID list endpoint and
the delete-user cascade. LinkDown/timeout/malformed payload all return
[] so callers don't repeat defensive parsing. 5 TDD unit tests cover
the happy path + three failure modes + None uart.
"
```

---

## Task 2: `GET /api/users/<name>/rfid.json` endpoint + tests

**Files:**
- Modify: `smart_gate/web/app.py`
- Modify: `tests/web/test_user_rfid_management.py`

- [ ] **Step 1: Add failing test**

Append to `tests/web/test_user_rfid_management.py`:

```python
def test_get_user_rfid_json(monkeypatch):
    """End-to-end: GET /api/users/<name>/rfid.json with a stubbed uart."""
    from smart_gate.web.app import create_app

    # Minimal mocks for the create_app contract
    db = Mock()
    db.get_user_id_by_name.return_value = 1
    hub = Mock()
    uart = Mock()
    uart.send_cmd.return_value = _ack([
        {"uid": "AAAA1111", "name": "alice"},
        {"uid": "CCCC3333", "name": "alice"},
        {"uid": "BBBB2222", "name": "bob"},
    ])

    app = create_app(db=db, hub=hub, uart=uart, data_dir="/tmp")
    app.config["TESTING"] = True
    client = app.test_client()

    r = client.get("/api/users/alice/rfid.json")
    assert r.status_code == 200
    assert r.get_json() == {"uids": ["AAAA1111", "CCCC3333"]}


def test_get_user_rfid_json_unknown_user():
    from smart_gate.web.app import create_app
    db = Mock()
    db.get_user_id_by_name.return_value = None
    hub = Mock()
    uart = Mock()

    app = create_app(db=db, hub=hub, uart=uart, data_dir="/tmp")
    client = app.test_client()

    r = client.get("/api/users/ghost/rfid.json")
    assert r.status_code == 404
    uart.send_cmd.assert_not_called()


def test_get_user_rfid_json_link_down(monkeypatch):
    from smart_gate.web.app import create_app
    db = Mock()
    db.get_user_id_by_name.return_value = 1
    hub = Mock()
    uart = Mock()
    uart.send_cmd.side_effect = LinkDown("no esp")

    app = create_app(db=db, hub=hub, uart=uart, data_dir="/tmp")
    client = app.test_client()

    r = client.get("/api/users/alice/rfid.json")
    # Helper returns [] on LinkDown; endpoint treats that as success-empty.
    # This is acceptable because the UI shows "no cards" either way.
    assert r.status_code == 200
    assert r.get_json() == {"uids": []}
```

- [ ] **Step 2: Run; expect 404 on the route**

Run: `cd /home/nguyenvd/workspace/smart_gate && python -m pytest tests/web/test_user_rfid_management.py -v -k "get_user_rfid"`
Expected: failures because route doesn't exist yet (404 from Flask itself, or AssertionError).

- [ ] **Step 3: Add the endpoint**

In `smart_gate/web/app.py`, immediately after the existing `api_add_rfid` route (around line 377), add:

```python
    @app.route("/api/users/<name>/rfid.json", methods=["GET"])
    def api_list_rfid(name: str):
        """List RFID UIDs bound to a given user in the ESP allowlist.

        Returns 200 with {"uids": [...]} even on LinkDown — the UI can't
        distinguish "no cards" from "no link" anyway, so the simplest
        consistent contract is "always 200, list may be empty."
        """
        if not re.match(r"^[A-Za-z0-9_\-]+$", name):
            return jsonify({"error": "invalid name"}), 400
        user_id = db.get_user_id_by_name(name)
        if user_id is None:
            return jsonify({"error": f"user not found: {name}"}), 404
        uids = _list_uids_for_user(uart, name)
        return jsonify({"uids": uids})
```

- [ ] **Step 4: Tests pass**

Run: `cd /home/nguyenvd/workspace/smart_gate && python -m pytest tests/web/test_user_rfid_management.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add smart_gate/web/app.py tests/web/test_user_rfid_management.py
git commit -m "feat(web): GET /api/users/<name>/rfid.json — list bound UIDs

Powers the chip list on /users page. Returns 200 with empty list on
LinkDown (UI shows 'no cards' either way; simpler contract than 503).
404 stays for unknown SQLite user. 3 new tests.
"
```

---

## Task 3: Cascade `cmd:remove_uid` in `DELETE /api/users/<name>` + tests

**Files:**
- Modify: `smart_gate/web/app.py` (existing `user_delete` route)
- Modify: `tests/web/test_user_rfid_management.py`

- [ ] **Step 1: Add failing tests**

Append:

```python
def test_delete_user_cascades_remove_uid():
    """DELETE /api/users/<name> first removes ESP allowlist entries."""
    from smart_gate.web.app import create_app
    db = Mock()
    db.delete_user.return_value = True
    hub = Mock()
    uart = Mock()
    # First call (list_uids): two UIDs; subsequent calls (remove_uid each): ok
    uart.send_cmd.side_effect = [
        _ack([{"uid": "AAAA", "name": "alice"},
              {"uid": "BBBB", "name": "alice"}]),
        {"data": {"ok": True}},
        {"data": {"ok": True}},
    ]

    app = create_app(db=db, hub=hub, uart=uart, data_dir="/tmp")
    client = app.test_client()

    r = client.delete("/api/users/alice")
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    assert sorted(body["removed_uids"]) == ["AAAA", "BBBB"]
    assert body.get("failed_uids", []) == []
    # Verify the call ordering: list_uids then two remove_uid
    calls = uart.send_cmd.call_args_list
    assert calls[0].args[0] == "list_uids"
    assert calls[1].args[0] == "remove_uid"
    assert calls[2].args[0] == "remove_uid"
    db.delete_user.assert_called_once_with("alice")


def test_delete_user_link_down_still_deletes_sqlite():
    from smart_gate.web.app import create_app
    db = Mock()
    db.delete_user.return_value = True
    hub = Mock()
    uart = Mock()
    uart.send_cmd.side_effect = LinkDown("no esp")

    app = create_app(db=db, hub=hub, uart=uart, data_dir="/tmp")
    client = app.test_client()

    r = client.delete("/api/users/alice")
    assert r.status_code == 200
    body = r.get_json()
    assert body["removed_uids"] == []
    assert body.get("link_down") is True
    db.delete_user.assert_called_once_with("alice")


def test_delete_user_partial_uid_failure():
    from smart_gate.web.app import create_app
    db = Mock()
    db.delete_user.return_value = True
    hub = Mock()
    uart = Mock()
    # list_uids ok, first remove_uid ok, second raises
    uart.send_cmd.side_effect = [
        _ack([{"uid": "AAAA", "name": "alice"},
              {"uid": "BBBB", "name": "alice"}]),
        {"data": {"ok": True}},
        LinkTimeout("esp slow"),
    ]

    app = create_app(db=db, hub=hub, uart=uart, data_dir="/tmp")
    client = app.test_client()

    r = client.delete("/api/users/alice")
    assert r.status_code == 200
    body = r.get_json()
    assert body["removed_uids"] == ["AAAA"]
    assert body["failed_uids"] == ["BBBB"]
    db.delete_user.assert_called_once_with("alice")
```

- [ ] **Step 2: Run; expect existing route to ignore UID cascade**

Run: `cd /home/nguyenvd/workspace/smart_gate && python -m pytest tests/web/test_user_rfid_management.py -v -k "delete_user"`
Expected: tests fail because current `user_delete` doesn't return `removed_uids` / `failed_uids` / `link_down` and doesn't call `uart.send_cmd`.

- [ ] **Step 3: Modify `user_delete` route**

Find the existing `def user_delete(name: str):` (around `app.py:297`). Replace its body so the function looks like:

```python
    @app.route("/api/users/<name>", methods=["DELETE", "POST"])
    def user_delete(name: str):
        """Delete a user. Cascades face_encodings + qr_tokens via FK,
        removes the QR PNG, triggers matcher reload, AND best-effort
        removes any RFID UIDs from the ESP allowlist so a deleted user's
        card can't keep opening the gate.

        Body keys in 200 response:
          ok: bool
          name: str
          removed_uids: list[str]    — uids successfully flushed from ESP
          failed_uids:  list[str]    — uids whose remove_uid command failed
          link_down:    bool         — true if list_uids couldn't talk to ESP
        """
        if request.method == "POST" and request.args.get("action") != "delete":
            return jsonify({"error": "use DELETE or POST?action=delete"}), 405
        if not re.match(r"^[A-Za-z0-9_\-]+$", name):
            return jsonify({"error": "invalid name"}), 400

        # 1. Best-effort ESP cascade — collect UIDs, then remove each.
        # Order matters: do this BEFORE SQLite delete so even a partial
        # failure leaves no SQLite row pointing at a still-allowlisted UID.
        removed_uids: list[str] = []
        failed_uids:  list[str] = []
        link_down = False
        uids_to_remove = _list_uids_for_user(uart, name) if uart is not None else []
        if uart is None or (uart is not None and not uids_to_remove):
            # Distinguish "no UIDs bound" from "link down" by probing:
            # if uart is None or _list_uids_for_user returned [] AND the
            # last call raised LinkDown, set link_down. Simpler: just try
            # a no-op probe via send_cmd only if uart exists and list was
            # empty — but that's an extra round-trip per delete. Cheaper:
            # mark link_down whenever uart is not None but list returned
            # [] AND a subsequent retry of list_uids also raises.
            # YAGNI here: only set link_down when uart is not None and the
            # initial list_uids itself raised — re-implement by inlining:
            pass
        # Re-implement above probing inline (the helper swallows errors):
        if uart is not None:
            try:
                ack = uart.send_cmd("list_uids", {}, timeout=2.0)
                # If we get here, link is up. Re-derive uids (we may have
                # gotten an empty list legitimately).
                if isinstance(ack, dict):
                    entries = (ack.get("data") or {}).get("uids") or []
                    uids_to_remove = [
                        e["uid"] for e in entries
                        if isinstance(e, dict)
                        and e.get("name") == name
                        and isinstance(e.get("uid"), str)
                    ]
            except (LinkDown, LinkTimeout):
                link_down = True
                uids_to_remove = []
                _emit_audit(esp_log_bus, "warn", "rfid",
                            f"delete user={name}: ESP link down, "
                            f"allowlist NOT flushed",
                            direction="←")

        for uid in uids_to_remove:
            try:
                uart.send_cmd("remove_uid", {"uid": uid}, timeout=2.0)
                removed_uids.append(uid)
            except (LinkDown, LinkTimeout, Exception):
                failed_uids.append(uid)
                log.warning("remove_uid failed for uid=%s during "
                            "delete user=%s", uid, name)
                _emit_audit(esp_log_bus, "warn", "rfid",
                            f"remove_uid FAILED uid={uid} during "
                            f"delete user={name}",
                            direction="←")

        # 2. SQLite cascade + QR PNG + matcher reload (existing flow).
        existed = db.delete_user(name)
        if not existed:
            return jsonify({"error": f"user {name} not found"}), 404
        qr_path = qr_dir / f"{name}.png"
        try:
            qr_path.unlink()
        except FileNotFoundError:
            pass
        if reload_event is not None:
            reload_event.set()
        elif matcher is not None:
            matcher.reload(db)
        log.info("deleted user %s (cascade encodings/tokens + qr png + "
                 "%d ESP UIDs)", name, len(removed_uids))
        return jsonify({
            "ok": True,
            "name": name,
            "removed_uids": removed_uids,
            "failed_uids": failed_uids,
            "link_down": link_down,
        })
```

- [ ] **Step 4: Simplify — remove the placeholder block**

The code above has a noted YAGNI block "Re-implement above probing inline."
After landing it, factor cleanly:

```python
        # 1. Best-effort ESP cascade.
        removed_uids: list[str] = []
        failed_uids:  list[str] = []
        link_down = False
        uids_to_remove: list[str] = []
        if uart is not None:
            try:
                ack = uart.send_cmd("list_uids", {}, timeout=2.0)
                entries = (ack.get("data") or {}).get("uids") or []
                uids_to_remove = [
                    e["uid"] for e in entries
                    if isinstance(e, dict)
                    and e.get("name") == name
                    and isinstance(e.get("uid"), str)
                ]
            except (LinkDown, LinkTimeout):
                link_down = True
                _emit_audit(esp_log_bus, "warn", "rfid",
                            f"delete user={name}: ESP link down, "
                            f"allowlist NOT flushed",
                            direction="←")
            except Exception:
                log.exception("list_uids during delete user=%s", name)
                link_down = True

        for uid in uids_to_remove:
            try:
                uart.send_cmd("remove_uid", {"uid": uid}, timeout=2.0)
                removed_uids.append(uid)
            except (LinkDown, LinkTimeout) as e:
                failed_uids.append(uid)
                log.warning("remove_uid failed for uid=%s: %s", uid, e)
                _emit_audit(esp_log_bus, "warn", "rfid",
                            f"remove_uid FAILED uid={uid} "
                            f"during delete user={name}",
                            direction="←")
            except Exception:
                failed_uids.append(uid)
                log.exception("remove_uid unexpected error uid=%s", uid)
```

(The duplicated logic with `_list_uids_for_user` is intentional here:
the cascade needs to distinguish LinkDown from empty-list to set
`link_down: true` in the response. Don't try to thread that signal back
through the helper — it would muddle the helper's contract.)

- [ ] **Step 5: Tests pass**

Run: `cd /home/nguyenvd/workspace/smart_gate && python -m pytest tests/web/test_user_rfid_management.py -v`
Expected: 11 passed.

Also run the broader web suite:
`cd /home/nguyenvd/workspace/smart_gate && python -m pytest tests/ -k "web" -v 2>&1 | tail -5`
Expected: no regression (existing delete-user tests still pass).

- [ ] **Step 6: Commit**

```bash
git add smart_gate/web/app.py tests/web/test_user_rfid_management.py
git commit -m "fix(web): cascade cmd:remove_uid on delete user — close security gap

Deleted user's RFID cards previously stayed in ESP NVS allowlist
forever (main.py:515 logs 'granted on ESP but unknown to Pi' silently
on every swipe). Now: list_uids → filter by name → remove_uid for each,
THEN SQLite delete. Best-effort: per-UID failures collected in
failed_uids; LinkDown sets link_down:true; SQLite delete proceeds
regardless so admin can always purge the SQLite row.
"
```

---

## Task 4: Dashboard modal — target picker + auto-fill

**Files:**
- Modify: `smart_gate/web/templates/dashboard.html`
- Modify: `smart_gate/web/static/app.css`

- [ ] **Step 1: Locate modal IIFE + RFID section**

Open `smart_gate/web/templates/dashboard.html`. Locate:
- `<dialog id="add-user-modal">` (~line 140) → the inner `<div id="au-rfid-section">` (~line 155)
- The IIFE that starts with `// --- Unified Add-user modal:` (~line 279)
- The `const uidInput = …` declaration (~line 292)
- `applyMode()` function (~line 299)
- `form.addEventListener('submit', …)` handler (~line 347)

- [ ] **Step 2: Extend RFID section markup**

Replace the inner content of `<div id="au-rfid-section" style="display:none;">` with:

```html
    <div id="au-rfid-section" style="display:none;">
      <div class="au-rfid-target">
        <label><input type="radio" name="au-rfid-target" value="new" checked> Tạo user mới</label>
        <label><input type="radio" name="au-rfid-target" value="existing"> Bind vào user có sẵn</label>
      </div>
      <div id="au-rfid-existing-row" style="display:none;">
        <label>
          <span>User:</span>
          <select id="au-rfid-existing-select"></select>
        </label>
      </div>
      <label>
        <span>UID hex:</span>
        <input id="au-rfid-uid" type="text"
               pattern="[0-9A-Fa-f]{4,24}"
               maxlength="24"
               placeholder="vd 23ac9f11">
      </label>
      <p class="muted">Quẹt thẻ trước đầu đọc → UID tự fill vào ô trên. Hoặc gõ trực tiếp.</p>
    </div>
```

- [ ] **Step 3: Wire auto-fill + target picker into IIFE**

Find the const block at the top of the IIFE and add references:

```js
  const targetRadios = form.elements['au-rfid-target'];
  const existingRow  = document.getElementById('au-rfid-existing-row');
  const existingSel  = document.getElementById('au-rfid-existing-select');
```

Add the auto-fill state + helpers (paste right after the const block, before `function currentMode()`):

```js
  // Auto-fill UID from /api/esp_log/stream while modal is in RFID mode.
  const UID_RE = /uid=([0-9A-Fa-f]{4,24})\b/;
  let rfidEs = null;
  function startRfidListen() {
    if (rfidEs) return;
    try { rfidEs = new EventSource('/api/esp_log/stream'); }
    catch (e) { rfidEs = null; return; }
    rfidEs.addEventListener('log', function (ev) {
      let item;
      try { item = JSON.parse(ev.data); } catch (e) { return; }
      if (item.tag !== 'rfid') return;
      const m = UID_RE.exec(item.msg || '');
      if (!m) return;
      uidInput.value = m[1].toUpperCase();
      uidInput.classList.remove('au-rfid-flash');
      void uidInput.offsetWidth;
      uidInput.classList.add('au-rfid-flash');
    });
  }
  function stopRfidListen() {
    if (!rfidEs) return;
    rfidEs.close();
    rfidEs = null;
  }

  function currentTarget() {
    const r = form.querySelector('input[name="au-rfid-target"]:checked');
    return r ? r.value : 'new';
  }
  function applyTarget() {
    const t = currentTarget();
    existingRow.style.display = (t === 'existing') ? '' : 'none';
    if (t === 'existing' && existingSel.options.length === 0) {
      // Lazy-load on first show.
      fetch('/api/users.json').then(function (r) { return r.json(); })
        .then(function (j) {
          const users = (j && j.users) || [];
          existingSel.innerHTML = '';
          users.forEach(function (u) {
            const opt = document.createElement('option');
            opt.value = u.name;
            opt.textContent = u.name;
            existingSel.appendChild(opt);
          });
        }).catch(function () { /* leave empty; submit will 404 */ });
    }
  }
  Array.prototype.forEach.call(targetRadios, function (r) {
    r.addEventListener('change', applyTarget);
  });
```

Update `applyMode()` to add the listener start/stop + target reset:

```js
  function applyMode() {
    const m = currentMode();
    if (m === 'face') {
      faceSec.style.display = '';
      rfidSec.style.display = 'none';
      submitBtn.textContent = 'Chụp + Tạo';
      uidInput.required = false;
      stopRfidListen();
    } else {
      faceSec.style.display = 'none';
      rfidSec.style.display = '';
      submitBtn.textContent = 'Tạo + Bind';
      uidInput.required = true;
      applyTarget();
      startRfidListen();
    }
  }
```

Wire stop into cancel + close + submit-finally:

```js
  cancelBtn.addEventListener('click', function () {
    if (modal.open) modal.close();
    stopRfidListen();
  });
  modal.addEventListener('close', stopRfidListen);
```

- [ ] **Step 4: Rewrite the submit handler's RFID branch to honor target**

Find the `if (mode === 'face')` branch in the submit handler. The `else` branch currently does new-user-then-bind. Replace the else branch with:

```js
      } else {
        // RFID mode — branch on target
        const target = currentTarget();
        const uidVal = (uidInput.value || '').trim();
        if (!/^[0-9A-Fa-f]{4,24}$/.test(uidVal)) {
          flashToast('✗ UID hex không hợp lệ (4-24 hex chars)', 'err');
          return;
        }
        let name;
        if (target === 'existing') {
          name = existingSel.value;
          if (!name) {
            flashToast('✗ Chưa chọn user', 'err');
            return;
          }
        } else {
          // Create new user_NNN first
          flashToast('Đang tạo user mới…', 'info');
          const r1 = await fetch('/api/enroll', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ face_capture: false }),
          });
          if (!r1.ok) {
            flashToast('✗ enroll: ' + (await r1.text()).slice(0, 100), 'err');
            return;
          }
          const d1 = await r1.json();
          name = d1.name;
        }
        const r2 = await fetch('/api/users/' + encodeURIComponent(name) + '/rfid', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ uid: uidVal }),
        });
        if (!r2.ok) {
          flashToast('✗ bind UID: ' + (await r2.text()).slice(0, 100), 'err');
          return;
        }
        flashToast('✓ ' + name + ' + UID ' + uidVal.toUpperCase(), 'info');
        modal.close();
      }
```

Add the `finally` to the surrounding try if not present:

```js
    try {
      // ... face + rfid branches
    } finally {
      submitBtn.disabled = false;
      stopRfidListen();
    }
```

- [ ] **Step 5: Append CSS for the flash + radio row**

Find the inline `<style>` block in dashboard.html (around line 174). Append:

```css
.au-rfid-target { display: flex; gap: 18px; }
@keyframes au-rfid-flash-kf {
  0%   { box-shadow: 0 0 0 2px #10b981; }
  100% { box-shadow: 0 0 0 0 transparent; }
}
.au-rfid-flash { animation: au-rfid-flash-kf 800ms ease-out; }
```

- [ ] **Step 6: JS syntax check**

Run:

```bash
cd /home/nguyenvd/workspace/smart_gate
python3 -c "
import re
m = re.search(r'<script>([\s\S]*?)</script>', open('smart_gate/web/templates/dashboard.html').read())
open('/tmp/_check.js','w').write(m.group(1))
"
node --check /tmp/_check.js && echo OK
```

Expected: `OK`.

- [ ] **Step 7: Run web test suite (no regression)**

Run: `cd /home/nguyenvd/workspace/smart_gate && python -m pytest tests/ -k "web" -v 2>&1 | tail -5`
Expected: all passing (no Python change in this task).

- [ ] **Step 8: Commit**

```bash
git add smart_gate/web/templates/dashboard.html
git commit -m "feat(web): Add-user modal — auto-fill UID + bind to existing user

Modal RFID mode grows two capabilities:
  1. SSE listener (mode-scoped) extracts uid=… from rfid log lines and
     populates the input with a brief green flash. EventSource opened on
     mode-into-RFID, closed on mode-out / cancel / dialog close /
     submit-finally.
  2. Radio above the UID field: 'Tạo user mới' (default) or 'Bind vào
     user có sẵn' → dropdown populated from /api/users.json. Existing-
     user path skips /api/enroll entirely, going straight to
     /api/users/<name>/rfid. Lets admins add a card to a user already
     created via Face without forking into two separate user_NNN rows.
"
```

---

## Task 5: `/users` page — UID chip list with × remove buttons

**Files:**
- Modify: `smart_gate/web/templates/users.html`
- Modify: `smart_gate/web/static/app.css`

- [ ] **Step 1: Add chip list to user row template**

Open `smart_gate/web/templates/users.html`. Inside the per-user row template (the `{% for u in users %}` block — find the existing `<form class="rfid-form">`), insert above the existing add-RFID form:

```html
<div class="uid-chips" data-user="{{ name }}">
  <span class="uid-chips-loading muted">đang tải UIDs…</span>
</div>
```

- [ ] **Step 2: Add fetch + render JS at the bottom of the `<script>` block**

At the end of the inline script in `users.html`, add:

```js
// Lazy-load UID chips per user row on first visible.
function loadUidChips(el) {
  if (el.dataset.loaded === '1') return;
  el.dataset.loaded = '1';
  const name = el.dataset.user;
  fetch('/api/users/' + encodeURIComponent(name) + '/rfid.json')
    .then(function (r) { return r.json(); })
    .then(function (j) {
      const uids = (j && j.uids) || [];
      el.innerHTML = '';
      if (uids.length === 0) {
        el.innerHTML = '<span class="muted">chưa có thẻ</span>';
        return;
      }
      uids.forEach(function (uid) {
        const chip = document.createElement('span');
        chip.className = 'uid-chip';
        chip.innerHTML = '<code>' +
          uid.replace(/[<>&"]/g, function (c) {
            return {'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;'}[c];
          }) +
          '</code> <button type="button" class="uid-chip-x" ' +
          'title="xóa UID này">&times;</button>';
        chip.querySelector('.uid-chip-x').addEventListener('click',
          function () { removeUid(name, uid, chip); });
        el.appendChild(chip);
      });
    })
    .catch(function () {
      el.innerHTML = '<span class="muted">lỗi tải UIDs</span>';
    });
}

function removeUid(name, uid, chipEl) {
  if (!confirm('Xóa UID ' + uid + ' khỏi ' + name + '?')) return;
  fetch('/api/users/' + encodeURIComponent(name)
        + '/rfid/' + encodeURIComponent(uid),
        { method: 'DELETE' })
    .then(function (r) {
      if (!r.ok) throw new Error('http ' + r.status);
      chipEl.remove();
    })
    .catch(function (e) {
      alert('Xóa UID thất bại: ' + e.message);
    });
}

document.querySelectorAll('.uid-chips').forEach(loadUidChips);
```

- [ ] **Step 3: Add CSS for chips**

Append to `smart_gate/web/static/app.css`:

```css
.uid-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
.uid-chip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 8px;
  background: rgba(59, 130, 246, 0.1);
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: 12px;
  font-size: 13px;
}
.uid-chip code {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
}
.uid-chip-x {
  background: none; border: none; color: #ef4444;
  font-size: 16px; line-height: 1; cursor: pointer;
  padding: 0 2px;
}
.uid-chip-x:hover { color: #b91c1c; }
```

- [ ] **Step 4: Syntax check**

Run:

```bash
cd /home/nguyenvd/workspace/smart_gate
python3 -c "
import re
m = re.search(r'<script>([\s\S]*?)</script>', open('smart_gate/web/templates/users.html').read())
open('/tmp/_check_users.js','w').write(m.group(1))
"
node --check /tmp/_check_users.js && echo OK
```

Expected: `OK`.

- [ ] **Step 5: pytest still green**

Run: `cd /home/nguyenvd/workspace/smart_gate && python -m pytest tests/ -k "web" -v 2>&1 | tail -5`
Expected: still passing.

- [ ] **Step 6: Commit**

```bash
git add smart_gate/web/templates/users.html smart_gate/web/static/app.css
git commit -m "feat(web): /users page — UID chips with × remove per user

Each user row fetches /api/users/<name>/rfid.json on load and renders
one .uid-chip per bound UID. × button confirms then DELETEs via the
existing /api/users/<name>/rfid/<uid> route, removing the chip on
success. 'chưa có thẻ' placeholder for users with no UIDs.
"
```

---

## Task 6: Deploy + manual verification on Pi

**Files:** (deploy only)

- [ ] **Step 1: Stage all 4 changed files to /tmp on Pi**

Run:

```bash
scp smart_gate/web/app.py                       pi@192.168.1.137:/tmp/app.py
scp smart_gate/web/templates/dashboard.html     pi@192.168.1.137:/tmp/dashboard.html
scp smart_gate/web/templates/users.html         pi@192.168.1.137:/tmp/users.html
scp smart_gate/web/static/app.css               pi@192.168.1.137:/tmp/app.css
```

- [ ] **Step 2: sudo-copy into /opt/smart-gate + chown + restart**

```bash
ssh pi@192.168.1.137 "
  sudo cp /tmp/app.py            /opt/smart-gate/smart_gate/web/app.py &&
  sudo cp /tmp/dashboard.html    /opt/smart-gate/smart_gate/web/templates/dashboard.html &&
  sudo cp /tmp/users.html        /opt/smart-gate/smart_gate/web/templates/users.html &&
  sudo cp /tmp/app.css           /opt/smart-gate/smart_gate/web/static/app.css &&
  sudo chown smart-gate:smart-gate \
      /opt/smart-gate/smart_gate/web/app.py \
      /opt/smart-gate/smart_gate/web/templates/dashboard.html \
      /opt/smart-gate/smart_gate/web/templates/users.html \
      /opt/smart-gate/smart_gate/web/static/app.css &&
  sudo systemctl restart smart-gate &&
  sleep 3 &&
  sudo systemctl is-active smart-gate
"
```

Expected: `active`.

- [ ] **Step 3: Served JS syntax check**

```bash
ssh pi@192.168.1.137 "curl -sS http://localhost:8080/" > /tmp/srv1.html
ssh pi@192.168.1.137 "curl -sS http://localhost:8080/users" > /tmp/srv2.html
python3 -c "
import re
for path in ['/tmp/srv1.html', '/tmp/srv2.html']:
    m = re.search(r'<script>([\s\S]*?)</script>', open(path).read())
    if m: open(path + '.js','w').write(m.group(1))
"
node --check /tmp/srv1.html.js && node --check /tmp/srv2.html.js && echo "all served JS OK"
```

Expected: `all served JS OK`.

- [ ] **Step 4: Manual — Feature 1 (auto-fill)**

Hard-refresh dashboard. Click `+ Tạo user mới` → switch to RFID radio →
quẹt thẻ mới. The `#au-rfid-uid` input must show the UID hex within ~1 s
with green border flash.

- [ ] **Step 5: Manual — Feature 2 (target picker)**

In the same modal:
- Pick "Bind vào user có sẵn" → dropdown populates with existing users.
- Pick a user that has Face encoding only.
- Quẹt thẻ (auto-fill UID).
- Click "Tạo + Bind". Toast: `✓ user_xxx + UID YYYYYY`.
- Go to `/users` page; the picked user now has 1 chip; no new `user_NNN`
  was created (verify user count unchanged).
- Reopen modal → switch to "Tạo user mới" → swipe → submit → new
  user_NNN row appears with 1 chip.

- [ ] **Step 6: Manual — Feature 3 (chip × remove)**

On `/users`: each row should show UID chips for its allowlist entries.
Click × on one chip → confirm dialog → chip disappears. Hard-refresh
the page; chip stays gone. Swipe that card → ESP denies.

- [ ] **Step 7: Manual — Feature 4 (delete user cascade)**

1. Create `user_test` with face + bind 2 RFID UIDs.
2. Click delete on `/users`. Confirm.
3. Response toast / network response includes `removed_uids: ["A","B"]`.
4. Swipe one of the deleted UIDs → ESP denies (not "granted on ESP but
   unknown to Pi"). Verify by watching live-log toast.

- [ ] **Step 8: Manual — Feature 4 negative (UART down)**

1. Power off ESP or unplug USB.
2. Click delete on a user with bound UIDs.
3. Response: `link_down: true, removed_uids: []`. SQLite delete still
   happens. Audit log line warns: "delete user=…: ESP link down".
4. Power ESP back on. The orphaned UIDs are still in NVS — admin can
   manually wipe via `curl -X DELETE /api/users/<old>/rfid/<uid>` IF the
   user-name is still in firmware (it is). Acceptable for this rare path.

---

## Done criteria

- 5 code commits + 1 optional deploy commit land on `feat/safety-fixes`.
- `pytest tests/web/test_user_rfid_management.py` → 11 passing.
- `pytest tests/ -k web` → no regression.
- `node --check` clean on dashboard.html, users.html (local + served).
- 7 manual checks pass: auto-fill, target=new, target=existing, chip
  remove, cascade-on-delete-positive, cascade-on-delete-uart-down,
  served-JS-syntax.

## Supersedes

This plan replaces `2026-06-13-rfid-auto-fill-uid.md` (commit `f65d243`).
The prior plan's Task 1 is folded into Task 4 here. The prior spec
(`2026-06-13-rfid-auto-fill-uid-design.md`, commit `8eb2d9c`) is similarly
superseded by the new design doc.

# RFID Auto-fill UID Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** While the Add-user modal is open in RFID mode, populate `#au-rfid-uid` automatically from the next swipe heard on `/api/esp_log/stream`. Pure client-side change in `dashboard.html`.

**Architecture:** A second `EventSource('/api/esp_log/stream')` is opened the moment the user switches into RFID mode in the open modal, closed on any of: mode-switch-out, cancel, modal close, or submit-finally. On `log` events whose `tag === "rfid"` and whose `msg` matches `/uid=([0-9A-Fa-f]{4,24})\b/`, the captured hex (uppercased) replaces the input value and triggers an 800 ms green-border CSS flash. Backend pipeline already publishes every RFID swipe (granted or denied) through the SSE audit channel — no server changes.

**Tech Stack:** Vanilla JS + EventSource (browser-native) + one CSS keyframe.

---

## Task 1: Add lifecycle-scoped SSE listener in modal IIFE + flash CSS

**Files:**
- Modify: `smart_gate/web/templates/dashboard.html`

- [ ] **Step 1: Locate the modal IIFE**

Open `smart_gate/web/templates/dashboard.html` and find the IIFE that starts with the comment `// --- Unified Add-user modal:` (around line 279 after our `quẹt` fix). Inside it, locate:

- The `const uidInput = document.getElementById('au-rfid-uid');` declaration
- The `applyMode()` function definition
- The `cancelBtn.addEventListener('click', …)` handler
- The `form.addEventListener('submit', async …)` handler

These are the integration points.

- [ ] **Step 2: Add UID regex + listener state below the const declarations**

Right after `if (!modal || !openBtn) return;` and before `function currentMode()`, insert:

```js
  // RFID auto-fill: while modal is in RFID mode, listen to the live ESP
  // log stream and copy any `uid=…` hex from rfid-tagged messages into the
  // input. Backend already publishes both granted/denied swipes through
  // /api/esp_log/stream (main.py:_audit with tag='rfid').
  const UID_RE = /uid=([0-9A-Fa-f]{4,24})\b/;
  let rfidEs = null;

  function startRfidListen() {
    if (rfidEs) return;
    try {
      rfidEs = new EventSource('/api/esp_log/stream');
    } catch (e) {
      rfidEs = null;
      return;
    }
    rfidEs.addEventListener('log', function (ev) {
      let item;
      try { item = JSON.parse(ev.data); } catch (e) { return; }
      if (item.tag !== 'rfid') return;
      const m = UID_RE.exec(item.msg || '');
      if (!m) return;
      uidInput.value = m[1].toUpperCase();
      uidInput.classList.remove('au-rfid-flash');
      // Reflow forces the animation to restart on consecutive swipes.
      void uidInput.offsetWidth;
      uidInput.classList.add('au-rfid-flash');
    });
  }

  function stopRfidListen() {
    if (!rfidEs) return;
    rfidEs.close();
    rfidEs = null;
  }
```

- [ ] **Step 3: Wire start/stop into `applyMode()`**

Modify the existing `applyMode()` function. Where it currently does:

```js
  function applyMode() {
    const m = currentMode();
    if (m === 'face') {
      faceSec.style.display = '';
      rfidSec.style.display = 'none';
      submitBtn.textContent = 'Chụp + Tạo';
      uidInput.required = false;
    } else {
      faceSec.style.display = 'none';
      rfidSec.style.display = '';
      submitBtn.textContent = 'Tạo + Bind';
      uidInput.required = true;
    }
  }
```

Add a single `startRfidListen()` / `stopRfidListen()` call inside the branches so it becomes:

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
      startRfidListen();
    }
  }
```

- [ ] **Step 4: Wire stop into cancel + modal-close + submit-finally**

(a) In the existing `cancelBtn.addEventListener('click', …)` body, after the `modal.close()` call, add `stopRfidListen();`. Final shape:

```js
  cancelBtn.addEventListener('click', function () {
    if (modal.open) modal.close();
    stopRfidListen();
  });
```

(b) Add a new `modal.addEventListener('close', stopRfidListen);` line immediately after the cancelBtn handler. This covers ESC key and backdrop-click closes that `<dialog>` fires `close` for.

(c) In the existing `form.addEventListener('submit', async function (e) { … })` body — find the trailing block where `submitBtn.disabled = true` is set inside the `try`. The function currently has a `try { … }` but no `finally`. Add one:

```js
    } catch (err) {
      flashToast('✗ ' + (err.message || err), 'err');
    } finally {
      submitBtn.disabled = false;
      stopRfidListen();
    }
```

Verify the existing try/catch shape before inserting — the spec-reviewed code in dashboard.html already has a `submitBtn.disabled = true` at the top of the try; the finally just adds the matching `disabled = false` + `stopRfidListen()`. If there is already a `finally` clause, just append `stopRfidListen();` inside it.

- [ ] **Step 5: Add CSS keyframe + class to inline `<style>` block**

Find the inline `<style>` block in dashboard.html (around line 174, the `.add-user-modal` rules). Append:

```css
@keyframes au-rfid-flash-kf {
  0%   { box-shadow: 0 0 0 2px #10b981; }
  100% { box-shadow: 0 0 0 0 transparent; }
}
.au-rfid-flash {
  animation: au-rfid-flash-kf 800ms ease-out;
}
```

- [ ] **Step 6: Verify JS still parses cleanly**

Run:

```bash
cd /home/nguyenvd/workspace/smart_gate
python3 -c "
import re
m = re.search(r'<script>([\s\S]*?)</script>', open('smart_gate/web/templates/dashboard.html').read())
open('/tmp/_check.js','w').write(m.group(1))
"
node --check /tmp/_check.js && echo "JS syntax OK"
```

Expected: `JS syntax OK`. If it fails, fix the syntax before proceeding (this catches stray unicode escapes, unbalanced braces, etc.).

- [ ] **Step 7: Run web test suite (no regression)**

Run: `cd /home/nguyenvd/workspace/smart_gate && python -m pytest tests/ -k "web" -v 2>&1 | tail -5`
Expected: 73 passing (same as before — no Python code changed).

- [ ] **Step 8: Commit**

```bash
git add smart_gate/web/templates/dashboard.html
git commit -m "feat(web): auto-fill UID in Add-user modal RFID mode

Listen to /api/esp_log/stream while the modal is open in RFID mode;
on log events with tag=rfid containing uid=AB12CD34, populate the
input and flash a green border for 800ms. EventSource scoped to
mode-rfid lifetime (start on switch-into-rfid, stop on switch-out,
cancel, dialog close, or submit-finally). Backend untouched — the
denial audit message already carries the UID.
"
```

---

## Task 2: Deploy + manual verification on Pi

**Files:** (deploy only)

- [ ] **Step 1: Stage + deploy to /opt/smart-gate**

Run:

```bash
scp /home/nguyenvd/workspace/smart_gate/smart_gate/web/templates/dashboard.html pi@192.168.1.137:/tmp/dashboard.html
ssh pi@192.168.1.137 "sudo cp /tmp/dashboard.html /opt/smart-gate/smart_gate/web/templates/dashboard.html && \
                     sudo chown smart-gate:smart-gate /opt/smart-gate/smart_gate/web/templates/dashboard.html && \
                     sudo systemctl restart smart-gate && \
                     sleep 3 && sudo systemctl is-active smart-gate"
```

Expected: `active`.

- [ ] **Step 2: Confirm served HTML still parses**

Run:

```bash
ssh pi@192.168.1.137 "curl -sS http://localhost:8080/" > /tmp/served_check.html
python3 -c "
import re
m = re.search(r'<script>([\s\S]*?)</script>', open('/tmp/served_check.html').read())
open('/tmp/served_check.js','w').write(m.group(1))
"
node --check /tmp/served_check.js && echo "served JS OK"
```

Expected: `served JS OK`.

- [ ] **Step 3: Browser manual verification — positive path**

In the browser:

1. Hard-refresh dashboard (Ctrl+Shift+R).
2. Open DevTools → Network → filter `EventStream` (or `eventsource`).
3. Click **+ Tạo user mới**. Modal opens in Face mode. Network: only the
   existing toast-IIFE EventSource (one connection).
4. Click the **RFID** radio. Network: a SECOND EventSource opens.
5. Quẹt thẻ MỚI (chưa enrolled) ở đầu đọc. Within ~1 s the `#au-rfid-uid`
   input populates with the UID hex (uppercase, no separators) and
   shows a brief green border flash.
6. Quẹt thẻ MỚI thứ hai. Input updates to the new UID and flashes again.
7. Click **Hủy**. Modal closes. Network: the second EventSource closes
   (status: `cancelled`/`finished`).

- [ ] **Step 4: Browser manual verification — lifecycle paths**

1. Open modal → RFID mode → switch back to Face mode. Network: the second
   EventSource closes.
2. Open modal → RFID mode → press ESC. Modal closes. Network: second ES
   closes (via the `close` event listener).
3. Open modal → RFID mode → swipe → click **Tạo + Bind**. After server
   round-trip the second ES closes (via the submit-finally branch).
4. Open modal → Face mode → swipe nearby. UID input is empty and stays
   empty (mode-scoped listener was never started — verify in Network
   that no second ES exists in this scenario).

- [ ] **Step 5: Browser manual verification — negative path**

1. Open modal → RFID mode.
2. Quẹt thẻ ĐÃ enrolled (granted). The Pi audit log shows `[info]` or no
   rfid msg (granted UID isn't logged with `uid=…` token by main.py).
   Confirm the UID input does NOT auto-fill — regex doesn't match
   granted-path messages.

(If it DOES auto-fill on granted, that's still acceptable behavior — the
admin can simply submit and the backend will see `user already exists`
or similar. Note any surprise but don't block on it.)

- [ ] **Step 6: Final commit (optional deploy record)**

Nothing to commit code-wise. If you want a record:

```bash
git commit --allow-empty -m "deploy: RFID auto-fill UID live on Pi"
```

---

## Done criteria

- One code commit landing on `feat/safety-fixes` (Task 1).
- `node --check` passes on both local and served `<script>` block.
- Existing 73 web tests still pass.
- Manual lifecycle tests confirm the second EventSource opens on
  switch-into-RFID and closes on every documented exit path.
- Swiping a new card while the modal is in RFID mode populates the UID
  field within ~1 s with a green border flash.

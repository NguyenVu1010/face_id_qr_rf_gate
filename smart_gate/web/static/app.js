// Smart Gate — admin UI sprinkles.
(function () {
  // -------------------------------------------------- UTC → browser-local time
  // SQLite stores events.ts / esp_log.ts as naive UTC strings (e.g.
  // "2026-06-12 20:34:52"). Render them in the browser's local timezone so
  // users in UTC+7 don't see times that look 7 hours stale.

  // Returns "HH:MM:SS" in local time, or the input as-is on parse failure.
  function utcToLocalTime(s) {
    if (!s) return '';
    var iso = String(s).replace(' ', 'T') + 'Z';
    var d = new Date(iso);
    if (isNaN(d.getTime())) return s;
    return d.toLocaleTimeString([], { hour12: false });
  }

  // Returns "YYYY-MM-DD HH:MM:SS" in local time, or the input as-is on parse
  // failure. Uses sortable ISO-ish ordering (not locale date format).
  function utcToLocalDateTime(s) {
    if (!s) return '';
    var iso = String(s).replace(' ', 'T') + 'Z';
    var d = new Date(iso);
    if (isNaN(d.getTime())) return s;
    var pad = function (n) { return n < 10 ? '0' + n : '' + n; };
    return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate())
      + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds());
  }

  // Walk a subtree and rewrite text content of elements that carry a raw
  // UTC string. Two flavors:
  //   <time class="ts-utc"      datetime="UTC string">…</time>  → HH:MM:SS
  //   <... class="ts-utc-full"  data-utc="UTC string">…</...>   → YYYY-MM-DD HH:MM:SS
  // The raw UTC string is preserved in the datetime / data-utc attribute so
  // tooltips, screen readers, and downstream JS can still see the source value.
  function applyLocalTime(root) {
    var scope = root || document;
    scope.querySelectorAll('.ts-utc').forEach(function (el) {
      var utc = el.getAttribute('datetime') || el.getAttribute('data-utc');
      if (!utc) return;
      el.textContent = utcToLocalTime(utc);
      if (!el.title) el.title = utc + ' UTC';
    });
    scope.querySelectorAll('.ts-utc-full').forEach(function (el) {
      var utc = el.getAttribute('data-utc') || el.getAttribute('datetime');
      if (!utc) return;
      el.textContent = utcToLocalDateTime(utc);
      if (!el.title) el.title = utc + ' UTC';
    });
  }

  // Expose for inline use (e.g. peripherals page builds DOM in JS).
  window.utcToLocalTime = utcToLocalTime;
  window.utcToLocalDateTime = utcToLocalDateTime;
  window.applyLocalTime = applyLocalTime;

  document.addEventListener('DOMContentLoaded', function () { applyLocalTime(); });
  document.body.addEventListener('htmx:afterSwap', function (e) {
    applyLocalTime(e.detail && e.detail.target ? e.detail.target : document);
  });

  // -------------------------------------------------- Toast on HTMX result
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
    if (!tgt || !tgt.dataset) return;
    const ok = e.detail.successful;
    const msg = tgt.dataset[ok ? 'toastOk' : 'toastErr'];
    if (msg) toast(msg, ok ? 'ok' : 'danger');
  });

  // -------------------------------------------------- Clip modal
  window.openClip = function (id, ts, user) {
    const dlg = document.getElementById('clip-modal');
    if (!dlg) return;
    document.getElementById('clip-title').textContent =
      `Event #${id} · ${ts} · ${user || '—'}`;
    const v = document.getElementById('clip-video');
    v.src = `/clips/${id}.mp4`;
    const dl = document.getElementById('clip-download');
    dl.href = `/clips/${id}.mp4`;
    dl.download = `event-${id}.mp4`;
    dlg.showModal();
    dlg.addEventListener('close', () => {
      v.pause();
      v.removeAttribute('src');
      v.load();
    }, { once: true });
  };

  // -------------------------------------------------- Clip-link delegated handler
  // event_rows.html uses data-* attributes rather than an inline onclick string,
  // so user-controlled fields (ts, user_name) can never inject JS.
  document.body.addEventListener('click', (e) => {
    const a = e.target.closest('a.clip-link');
    if (!a) return;
    e.preventDefault();
    window.openClip(
      parseInt(a.dataset.eventId, 10),
      a.dataset.ts || '',
      a.dataset.user || ''
    );
  });

  // -------------------------------------------------- maxEventId helper (events page)
  window.maxEventId = function () {
    let m = 0;
    document.querySelectorAll('#events-tbody tr[data-event-id]').forEach((tr) => {
      m = Math.max(m, parseInt(tr.dataset.eventId, 10) || 0);
    });
    return m;
  };

  // -------------------------------------------------- minEventId helper (load older)
  window.minEventId = function () {
    let m = Infinity;
    document.querySelectorAll('#events-tbody tr[data-event-id]').forEach((tr) => {
      const id = parseInt(tr.dataset.eventId, 10);
      if (id && id < m) m = id;
    });
    return m === Infinity ? 0 : m;
  };

  // -------------------------------------------------- Diagnostic buttons (system page)
  document.body.addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-diag]');
    if (!btn) return;
    const verb = btn.dataset.diag;
    const dlg = document.getElementById('diag-modal');
    const out = document.getElementById('diag-result');
    if (!dlg || !out) return;
    document.getElementById('diag-title').textContent = `cmd:${verb}`;
    out.textContent = 'sending…';
    dlg.showModal();
    try {
      const r = await fetch(`/api/diag/${verb}`, { method: 'POST' });
      const body = await r.json();
      out.textContent = JSON.stringify(body, null, 2);
    } catch (err) {
      out.textContent = `request failed: ${err}`;
    }
  });

  // -------------------------------------------------- SSE: ESP32 log (system page only)
  const logList = document.getElementById('esp-log');
  if (logList) {
    let paused = false;
    const CAPACITY = 500;
    const status = document.getElementById('sse-status');

    document.getElementById('log-pause')?.addEventListener('click', (e) => {
      paused = !paused;
      e.target.textContent = paused ? 'Resume' : 'Pause';
    });
    document.getElementById('log-clear')?.addEventListener('click', () => {
      logList.innerHTML = '';
    });

    function lvlPillClass(lvl) {
      const l = (lvl || 'info').toLowerCase();
      return ['info', 'warn', 'error', 'debug'].includes(l)
        ? `pill pill-${l}` : 'pill pill-info';
    }
    // 5-char escape: covers attribute injection too (we use this value
    // inside datetime="..." and title="..." below, so " and ' matter).
    function escape(s) {
      return String(s == null ? '' : s).replace(/[&<>"']/g,
        c => ({
          '&': '&amp;',
          '<': '&lt;',
          '>': '&gt;',
          '"': '&quot;',
          "'": '&#39;'
        }[c]));
    }

    const es = new EventSource('/api/esp_log/stream');
    es.addEventListener('log', (e) => {
      if (paused) return;
      const r = JSON.parse(e.data);
      const li = document.createElement('li');
      li.dataset.lvl = (r.lvl || 'info').toLowerCase();
      const tsUtc = r.ts || '';
      const tsLocal = tsUtc ? utcToLocalTime(tsUtc) : '—';
      li.innerHTML =
        `<time class="ts-utc" datetime="${escape(tsUtc)}" title="${escape(tsUtc)} UTC">${escape(tsLocal)}</time>` +
        `<span class="${lvlPillClass(r.lvl)}">${escape(r.lvl || 'info')}</span>` +
        `<span class="tag">${escape(r.tag || '')}</span>` +
        `<span class="msg">${escape(r.msg)}</span>`;
      logList.insertBefore(li, logList.firstChild);
      while (logList.children.length > CAPACITY) logList.lastChild.remove();
    });
    es.onopen = () => {
      if (!status) return;
      status.className = 'pill pill-ok';
      status.innerHTML = '<span class="dot dot-ok"></span> live';
    };
    es.onerror = () => {
      if (!status) return;
      status.className = 'pill pill-warn';
      status.innerHTML = '<span class="dot dot-warn"></span> reconnecting…';
    };
  }
})();

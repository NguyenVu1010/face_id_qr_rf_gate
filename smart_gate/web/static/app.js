// Smart Gate — admin UI sprinkles.
(function () {
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

  // -------------------------------------------------- maxEventId helper (events page)
  window.maxEventId = function () {
    let m = 0;
    document.querySelectorAll('#events-tbody tr[data-event-id]').forEach((tr) => {
      m = Math.max(m, parseInt(tr.dataset.eventId, 10) || 0);
    });
    return m;
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
    function escape(s) {
      return String(s || '').replace(/[<>&]/g,
        c => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' }[c]));
    }

    const es = new EventSource('/api/esp_log/stream');
    es.addEventListener('log', (e) => {
      if (paused) return;
      const r = JSON.parse(e.data);
      const li = document.createElement('li');
      li.dataset.lvl = (r.lvl || 'info').toLowerCase();
      li.innerHTML =
        `<time>${(r.ts || '').slice(11, 19) || '—'}</time>` +
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

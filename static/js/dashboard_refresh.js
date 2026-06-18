(() => {
  const REFRESH_SECONDS = 600;
  const STATUS_POLL_SECONDS = 60;
  const STORAGE_KEY_PAUSED = 'jom.autoRefreshPaused';
  const STORAGE_KEY_LAST_RELOAD = 'jom.lastReloadAt';

  function pad(num) {
    return String(num).padStart(2, '0');
  }

  function formatCountdown(totalSeconds) {
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    return `${pad(mins)}:${pad(secs)}`;
  }

  function asText(value, fallback = '—') {
    if (value === null || value === undefined || value === '') return fallback;
    return String(value);
  }

  function isPaused() {
    return localStorage.getItem(STORAGE_KEY_PAUSED) === '1';
  }

  function setPaused(value) {
    localStorage.setItem(STORAGE_KEY_PAUSED, value ? '1' : '0');
  }

  function nowIso() {
    return new Date().toLocaleString();
  }

  function ensureStyles() {
    if (document.getElementById('jom-auto-refresh-styles')) return;
    const style = document.createElement('style');
    style.id = 'jom-auto-refresh-styles';
    style.textContent = `
      #jom-auto-refresh-badge {
        position: fixed;
        right: 16px;
        bottom: 16px;
        z-index: 9999;
        width: 320px;
        max-width: calc(100vw - 32px);
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 14px;
        background: rgba(16, 20, 28, 0.88);
        color: #e8edf7;
        backdrop-filter: blur(14px);
        box-shadow: 0 10px 28px rgba(0,0,0,0.28);
        font: 13px/1.4 system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
        overflow: hidden;
      }
      #jom-auto-refresh-badge * { box-sizing: border-box; }
      #jom-auto-refresh-badge .jom-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        padding: 12px 14px 8px;
      }
      #jom-auto-refresh-badge .jom-title {
        display: flex;
        align-items: center;
        gap: 8px;
        font-weight: 700;
        letter-spacing: 0.2px;
      }
      #jom-auto-refresh-badge .jom-dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        background: #22c55e;
        box-shadow: 0 0 0 3px rgba(34,197,94,0.18);
      }
      #jom-auto-refresh-badge .jom-dot.warn { background: #f59e0b; box-shadow: 0 0 0 3px rgba(245,158,11,0.18); }
      #jom-auto-refresh-badge .jom-dot.error { background: #ef4444; box-shadow: 0 0 0 3px rgba(239,68,68,0.18); }
      #jom-auto-refresh-badge .jom-body {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 10px;
        padding: 0 14px 10px;
      }
      #jom-auto-refresh-badge .jom-card {
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 10px;
        padding: 8px 10px;
        background: rgba(255,255,255,0.03);
        min-height: 62px;
      }
      #jom-auto-refresh-badge .jom-label {
        color: #96a2b8;
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.4px;
        margin-bottom: 4px;
      }
      #jom-auto-refresh-badge .jom-value {
        font-weight: 600;
        word-break: break-word;
      }
      #jom-auto-refresh-badge .jom-actions {
        display: flex;
        gap: 8px;
        padding: 0 14px 14px;
      }
      #jom-auto-refresh-badge .jom-btn {
        appearance: none;
        border: 1px solid rgba(255,255,255,0.12);
        background: rgba(255,255,255,0.05);
        color: #e8edf7;
        border-radius: 9px;
        padding: 7px 10px;
        cursor: pointer;
        font: inherit;
      }
      #jom-auto-refresh-badge .jom-btn:hover {
        background: rgba(255,255,255,0.1);
      }
      #jom-auto-refresh-badge .jom-footer {
        padding: 0 14px 12px;
        color: #96a2b8;
        font-size: 11px;
      }
      @media (max-width: 640px) {
        #jom-auto-refresh-badge { width: calc(100vw - 24px); right: 12px; bottom: 12px; }
        #jom-auto-refresh-badge .jom-body { grid-template-columns: 1fr; }
      }
    `;
    document.head.appendChild(style);
  }

  function ensureBadge() {
    if (document.getElementById('jom-auto-refresh-badge')) {
      return document.getElementById('jom-auto-refresh-badge');
    }
    ensureStyles();
    const badge = document.createElement('aside');
    badge.id = 'jom-auto-refresh-badge';
    badge.innerHTML = `
      <div class="jom-head">
        <div class="jom-title"><span class="jom-dot" id="jom-refresh-dot"></span><span>Live Runtime</span></div>
        <div id="jom-runtime-mode">runtime</div>
      </div>
      <div class="jom-body">
        <div class="jom-card">
          <div class="jom-label">Source file</div>
          <div class="jom-value" id="jom-source-file">—</div>
        </div>
        <div class="jom-card">
          <div class="jom-label">Next refresh</div>
          <div class="jom-value" id="jom-countdown">10:00</div>
        </div>
        <div class="jom-card">
          <div class="jom-label">Source status</div>
          <div class="jom-value" id="jom-source-status">Checking…</div>
        </div>
        <div class="jom-card">
          <div class="jom-label">Last check</div>
          <div class="jom-value" id="jom-last-check">—</div>
        </div>
      </div>
      <div class="jom-actions">
        <button class="jom-btn" id="jom-toggle-refresh" type="button">Pause refresh</button>
        <button class="jom-btn" id="jom-refresh-now" type="button">Refresh now</button>
      </div>
      <div class="jom-footer" id="jom-footer-text">Backend refresh target: every 600 seconds.</div>
    `;
    document.body.appendChild(badge);
    return badge;
  }

  const state = {
    countdown: REFRESH_SECONDS,
    lastCheck: null,
    sourceFile: null,
    sourceMode: null,
    sourceError: null,
    sitesCount: null,
  };

  function updateBadge() {
    const dot = document.getElementById('jom-refresh-dot');
    const sourceFile = document.getElementById('jom-source-file');
    const sourceStatus = document.getElementById('jom-source-status');
    const lastCheck = document.getElementById('jom-last-check');
    const countdown = document.getElementById('jom-countdown');
    const runtimeMode = document.getElementById('jom-runtime-mode');
    const footer = document.getElementById('jom-footer-text');
    const toggleBtn = document.getElementById('jom-toggle-refresh');

    if (!dot || !sourceFile || !sourceStatus || !lastCheck || !countdown || !runtimeMode || !footer || !toggleBtn) return;

    runtimeMode.textContent = asText(state.sourceMode, 'runtime');
    sourceFile.textContent = asText(state.sourceFile, '—');
    countdown.textContent = formatCountdown(state.countdown);
    lastCheck.textContent = state.lastCheck ? state.lastCheck : '—';
    toggleBtn.textContent = isPaused() ? 'Resume refresh' : 'Pause refresh';

    if (state.sourceError) {
      dot.className = 'jom-dot error';
      sourceStatus.textContent = `Error: ${state.sourceError}`;
      footer.textContent = 'Source error detected. Auto-refresh remains enabled unless paused.';
      return;
    }

    if (state.sourceFile) {
      dot.className = 'jom-dot';
      sourceStatus.textContent = `Sites: ${asText(state.sitesCount, '—')}`;
      footer.textContent = isPaused()
        ? 'Auto-refresh paused in this browser. Backend loop can keep running.'
        : 'Auto-refresh armed for a full page reload every 600 seconds.';
      return;
    }

    dot.className = 'jom-dot warn';
    sourceStatus.textContent = 'Waiting for source-state response…';
    footer.textContent = 'The page will reload every 600 seconds unless paused.';
  }

  async function pollSourceState() {
    try {
      const response = await fetch('/api/source-state', { cache: 'no-store', credentials: 'same-origin' });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();
      state.sourceFile = data.source_file || null;
      state.sourceMode = data.source_mode || 'runtime';
      state.sourceError = data.source_error || null;
      state.sitesCount = data.sites_count ?? null;
      state.lastCheck = nowIso();
      updateBadge();
    } catch (error) {
      state.sourceError = error && error.message ? error.message : String(error);
      state.lastCheck = nowIso();
      updateBadge();
    }
  }

  function refreshNow() {
    sessionStorage.setItem(STORAGE_KEY_LAST_RELOAD, String(Date.now()));
    window.location.reload();
  }

  function tick() {
    if (!isPaused()) {
      state.countdown = Math.max(0, state.countdown - 1);
      if (state.countdown === 0) {
        refreshNow();
        return;
      }
    }
    updateBadge();
  }

  function wireActions() {
    const toggleBtn = document.getElementById('jom-toggle-refresh');
    const refreshBtn = document.getElementById('jom-refresh-now');
    if (toggleBtn) {
      toggleBtn.addEventListener('click', () => {
        setPaused(!isPaused());
        updateBadge();
      });
    }
    if (refreshBtn) {
      refreshBtn.addEventListener('click', refreshNow);
    }
  }

  function start() {
    ensureBadge();
    wireActions();
    updateBadge();
    pollSourceState();
    setInterval(tick, 1000);
    setInterval(pollSourceState, STATUS_POLL_SECONDS * 1000);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start, { once: true });
  } else {
    start();
  }
})();

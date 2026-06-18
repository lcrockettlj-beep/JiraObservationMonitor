(() => {
  const REFRESH_SECONDS = 600;
  const STATUS_POLL_SECONDS = 60;
  const DATA_POLL_SECONDS = 60;
  const STORAGE_KEY_PAUSED = 'jom.autoRefreshPaused';
  const STORAGE_KEY_COLLAPSED = 'jom.autoRefreshCollapsed';

  const state = {
    countdown: REFRESH_SECONDS,
    sourceFile: null,
    sourceMode: 'runtime',
    sourceError: null,
    sitesCount: null,
    lastCheck: null,
    lastBackendRun: null,
    health: 'healthy',
    healthLabel: 'Healthy',
    insights: [],
  };

  function pad(num) { return String(num).padStart(2, '0'); }
  function formatCountdown(totalSeconds) {
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    return `${pad(mins)}:${pad(secs)}`;
  }
  function asText(value, fallback = '—') {
    if (value === null || value === undefined || value === '') return fallback;
    return String(value);
  }
  function isPaused() { return localStorage.getItem(STORAGE_KEY_PAUSED) === '1'; }
  function setPaused(value) { localStorage.setItem(STORAGE_KEY_PAUSED, value ? '1' : '0'); }
  function isCollapsed() { return localStorage.getItem(STORAGE_KEY_COLLAPSED) === '1'; }
  function setCollapsed(value) { localStorage.setItem(STORAGE_KEY_COLLAPSED, value ? '1' : '0'); }
  function nowLocal() { return new Date().toLocaleString(); }

  function ensureStyles() {
    if (document.getElementById('jom-runtime-alert-styles')) return;
    const style = document.createElement('style');
    style.id = 'jom-runtime-alert-styles';
    style.textContent = `
      #jom-auto-refresh-badge {
        position: fixed;
        right: 14px;
        bottom: 14px;
        z-index: 9999;
        width: 248px;
        max-width: calc(100vw - 24px);
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 14px;
        background: rgba(24, 28, 36, 0.95);
        color: #eef2f8;
        backdrop-filter: blur(14px);
        box-shadow: 0 12px 28px rgba(0,0,0,0.27);
        font: 12px/1.3 system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
        overflow: hidden;
        transition: transform 180ms ease, box-shadow 180ms ease, border-color 180ms ease;
      }
      #jom-auto-refresh-badge * { box-sizing: border-box; }
      #jom-auto-refresh-badge.jom-healthy {
        border-color: rgba(34,197,94,0.26);
        box-shadow: 0 12px 28px rgba(0,0,0,0.27), 0 0 20px rgba(34,197,94,0.22), 0 0 34px rgba(34,197,94,0.10);
      }
      #jom-auto-refresh-badge.jom-warning {
        border-color: rgba(245,158,11,0.34);
        box-shadow: 0 12px 28px rgba(0,0,0,0.29), 0 0 24px rgba(245,158,11,0.30), 0 0 42px rgba(245,158,11,0.14);
        animation: jomPanelPulseWarn 1.9s ease-in-out infinite;
      }
      #jom-auto-refresh-badge.jom-critical {
        border-color: rgba(239,68,68,0.42);
        box-shadow: 0 12px 30px rgba(0,0,0,0.31), 0 0 28px rgba(239,68,68,0.36), 0 0 48px rgba(239,68,68,0.18);
        animation: jomPanelPulseCritical 1.1s ease-in-out infinite;
      }
      #jom-auto-refresh-badge.jom-collapsed {
        width: auto;
        min-width: 176px;
      }
      #jom-auto-refresh-badge .jom-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        padding: 9px 10px 7px;
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
        box-shadow: 0 0 0 3px rgba(34,197,94,0.24), 0 0 10px rgba(34,197,94,0.30);
      }
      #jom-auto-refresh-badge .jom-dot.warn {
        background: #f59e0b;
        box-shadow: 0 0 0 3px rgba(245,158,11,0.28), 0 0 12px rgba(245,158,11,0.34);
      }
      #jom-auto-refresh-badge .jom-dot.error {
        background: #ef4444;
        box-shadow: 0 0 0 3px rgba(239,68,68,0.32), 0 0 14px rgba(239,68,68,0.38);
      }
      #jom-auto-refresh-badge .jom-meta {
        display: flex;
        align-items: center;
        gap: 6px;
        color: #aeb8c9;
      }
      #jom-auto-refresh-badge .jom-mini-btn,
      #jom-auto-refresh-badge .jom-btn {
        appearance: none;
        border: 1px solid rgba(255,255,255,0.12);
        background: rgba(255,255,255,0.04);
        color: #eef2f8;
        cursor: pointer;
        font: inherit;
      }
      #jom-auto-refresh-badge .jom-mini-btn {
        border-radius: 8px;
        padding: 4px 7px;
      }
      #jom-auto-refresh-badge .jom-mini-btn:hover,
      #jom-auto-refresh-badge .jom-btn:hover { background: rgba(255,255,255,0.1); }
      #jom-auto-refresh-badge .jom-body {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 7px;
        padding: 0 10px 8px;
      }
      #jom-auto-refresh-badge .jom-card {
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 10px;
        padding: 7px 8px;
        background: rgba(255,255,255,0.03);
        min-height: 54px;
      }
      #jom-auto-refresh-badge .jom-label {
        color: #98a5bb;
        font-size: 10px;
        text-transform: uppercase;
        letter-spacing: 0.44px;
        margin-bottom: 4px;
      }
      #jom-auto-refresh-badge .jom-value {
        font-weight: 700;
        word-break: break-word;
      }
      #jom-auto-refresh-badge .jom-actions {
        display: flex;
        gap: 8px;
        padding: 0 10px 9px;
      }
      #jom-auto-refresh-badge .jom-btn {
        border-radius: 9px;
        padding: 6px 9px;
      }
      #jom-auto-refresh-badge .jom-footer {
        padding: 0 10px 10px;
        color: #96a2b8;
        font-size: 11px;
      }
      #jom-auto-refresh-badge .jom-insights {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        padding: 0 10px 9px;
      }
      #jom-auto-refresh-badge .jom-pill {
        border-radius: 999px;
        padding: 4px 8px;
        background: rgba(255,255,255,0.06);
        border: 1px solid rgba(255,255,255,0.08);
        color: #dce3ef;
        font-size: 11px;
      }
      #jom-auto-refresh-badge .jom-hidden { display: none !important; }
      @keyframes jomPanelPulseWarn {
        0%,100% { box-shadow: 0 12px 28px rgba(0,0,0,0.29), 0 0 20px rgba(245,158,11,0.26), 0 0 36px rgba(245,158,11,0.12); }
        50% { box-shadow: 0 12px 28px rgba(0,0,0,0.29), 0 0 32px rgba(245,158,11,0.42), 0 0 54px rgba(245,158,11,0.22); }
      }
      @keyframes jomPanelPulseCritical {
        0%,100% { box-shadow: 0 12px 30px rgba(0,0,0,0.31), 0 0 24px rgba(239,68,68,0.30), 0 0 44px rgba(239,68,68,0.16); }
        50% { box-shadow: 0 12px 30px rgba(0,0,0,0.31), 0 0 40px rgba(239,68,68,0.50), 0 0 68px rgba(239,68,68,0.28); }
      }
      @media (max-width: 640px) {
        #jom-auto-refresh-badge { width: calc(100vw - 20px); right: 10px; bottom: 10px; }
        #jom-auto-refresh-badge .jom-body { grid-template-columns: 1fr; }
      }
    `;
    document.head.appendChild(style);
  }

  function ensureBadge() {
    let badge = document.getElementById('jom-auto-refresh-badge');
    if (badge) return badge;
    ensureStyles();
    badge = document.createElement('aside');
    badge.id = 'jom-auto-refresh-badge';
    badge.innerHTML = `
      <div class="jom-head">
        <div class="jom-title"><span class="jom-dot" id="jom-refresh-dot"></span><span>Live Runtime</span></div>
        <div class="jom-meta"><span id="jom-runtime-mode">runtime</span><button class="jom-mini-btn" id="jom-toggle-collapse" type="button">Collapse</button></div>
      </div>
      <div id="jom-detail-wrap">
        <div class="jom-body">
          <div class="jom-card"><div class="jom-label">Source file</div><div class="jom-value" id="jom-source-file">—</div></div>
          <div class="jom-card"><div class="jom-label">Next refresh</div><div class="jom-value" id="jom-countdown">10:00</div></div>
          <div class="jom-card"><div class="jom-label">Source status</div><div class="jom-value" id="jom-source-status">Checking…</div></div>
          <div class="jom-card"><div class="jom-label">Last backend run</div><div class="jom-value" id="jom-last-backend">—</div></div>
        </div>
        <div class="jom-insights" id="jom-insights"></div>
        <div class="jom-actions">
          <button class="jom-btn" id="jom-toggle-refresh" type="button">Pause refresh</button>
          <button class="jom-btn" id="jom-refresh-now" type="button">Refresh now</button>
        </div>
        <div class="jom-footer" id="jom-footer-text">Backend refresh target: every 600 seconds.</div>
      </div>`;
    document.body.appendChild(badge);
    return badge;
  }

  function applyCollapsedState() {
    const badge = document.getElementById('jom-auto-refresh-badge');
    const wrap = document.getElementById('jom-detail-wrap');
    const btn = document.getElementById('jom-toggle-collapse');
    if (!badge || !wrap || !btn) return;
    if (isCollapsed()) {
      badge.classList.add('jom-collapsed');
      wrap.classList.add('jom-hidden');
      btn.textContent = 'Expand';
    } else {
      badge.classList.remove('jom-collapsed');
      wrap.classList.remove('jom-hidden');
      btn.textContent = 'Collapse';
    }
  }

  function setHealthClass() {
    const badge = document.getElementById('jom-auto-refresh-badge');
    const dot = document.getElementById('jom-refresh-dot');
    if (!badge || !dot) return;
    badge.classList.remove('jom-healthy', 'jom-warning', 'jom-critical');
    dot.classList.remove('warn', 'error');
    if (state.health === 'critical') {
      badge.classList.add('jom-critical');
      dot.classList.add('error');
      return;
    }
    if (state.health === 'warning') {
      badge.classList.add('jom-warning');
      dot.classList.add('warn');
      return;
    }
    badge.classList.add('jom-healthy');
  }

  function inferHealth(data) {
    if (state.sourceError) return { level: 'critical', label: 'Source error', insights: ['Source-state error detected'] };
    const criticalSites = Array.isArray(data?.critical_sites) ? data.critical_sites.length : 0;
    const warningSites = Array.isArray(data?.warning_sites) ? data.warning_sites.length : 0;
    const summary = data?.intelligence_summary || data?.intelligence || {};
    const topRisks = Array.isArray(summary?.top_risks) ? summary.top_risks : [];
    const insights = [];
    if (criticalSites > 0) insights.push(`${criticalSites} critical site${criticalSites === 1 ? '' : 's'}`);
    if (warningSites > 0) insights.push(`${warningSites} warning site${warningSites === 1 ? '' : 's'}`);
    if (topRisks.length > 0) insights.push(`${topRisks.length} intelligence risk${topRisks.length === 1 ? '' : 's'}`);
    if (criticalSites > 0) return { level: 'critical', label: 'Critical attention', insights };
    if (warningSites > 0 || topRisks.length > 0) return { level: 'warning', label: 'Warning attention', insights };
    return { level: 'healthy', label: 'Healthy', insights: insights.length ? insights : ['No active runtime alerts'] };
  }

  function updateInsights() {
    const wrap = document.getElementById('jom-insights');
    if (!wrap) return;
    wrap.innerHTML = '';
    const items = state.insights && state.insights.length ? state.insights : [`State: ${state.healthLabel}`];
    for (const item of items.slice(0,4)) {
      const pill = document.createElement('span');
      pill.className = 'jom-pill';
      pill.textContent = item;
      wrap.appendChild(pill);
    }
  }

  function updateBadge() {
    const sourceFile = document.getElementById('jom-source-file');
    const sourceStatus = document.getElementById('jom-source-status');
    const lastBackend = document.getElementById('jom-last-backend');
    const countdown = document.getElementById('jom-countdown');
    const runtimeMode = document.getElementById('jom-runtime-mode');
    const footer = document.getElementById('jom-footer-text');
    const toggleBtn = document.getElementById('jom-toggle-refresh');
    if (!sourceFile || !sourceStatus || !lastBackend || !countdown || !runtimeMode || !footer || !toggleBtn) return;
    runtimeMode.textContent = asText(state.sourceMode, 'runtime');
    sourceFile.textContent = asText(state.sourceFile, '—');
    sourceStatus.textContent = state.sourceError ? `Error: ${state.sourceError}` : `Sites: ${asText(state.sitesCount, '—')} • ${state.healthLabel}`;
    lastBackend.textContent = asText(state.lastBackendRun, state.lastCheck || '—');
    countdown.textContent = formatCountdown(state.countdown);
    toggleBtn.textContent = isPaused() ? 'Resume refresh' : 'Pause refresh';
    footer.textContent = isPaused() ? 'Auto-refresh paused in this browser. Backend loop can keep running.' : 'Auto-refresh armed for a full page reload every 600 seconds.';
    setHealthClass();
    updateInsights();
    applyCollapsedState();
  }

  async function pollSourceState() {
    try {
      const response = await fetch('/api/source-state', { cache: 'no-store', credentials: 'same-origin' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      state.sourceFile = data.source_file || null;
      state.sourceMode = data.source_mode || 'runtime';
      state.sourceError = data.source_error || null;
      state.sitesCount = data.sites_count ?? null;
      state.lastCheck = nowLocal();
      updateBadge();
    } catch (error) {
      state.sourceError = error && error.message ? error.message : String(error);
      state.lastCheck = nowLocal();
      state.health = 'critical';
      state.healthLabel = 'Source error';
      state.insights = ['Source-state poll failed'];
      updateBadge();
    }
  }

  async function pollRuntimeData() {
    try {
      const response = await fetch('/api/data', { cache: 'no-store', credentials: 'same-origin' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      const inferred = inferHealth(data);
      state.health = inferred.level;
      state.healthLabel = inferred.label;
      state.insights = inferred.insights || [];
      const estate = data?.estate || {};
      const latestSnapshot = data?.latest_snapshot_entry || {};
      state.lastBackendRun = estate.run_timestamp_local || latestSnapshot.snapshot_timestamp || latestSnapshot.created_at_local || state.lastBackendRun;
      updateBadge();
    } catch (error) {
      state.health = 'warning';
      state.healthLabel = 'Runtime check degraded';
      state.insights = ['Could not poll /api/data'];
      updateBadge();
    }
  }

  function refreshNow() { window.location.reload(); }
  function tick() {
    if (!isPaused()) {
      state.countdown = Math.max(0, state.countdown - 1);
      if (state.countdown === 0) { refreshNow(); return; }
    }
    updateBadge();
  }

  function wireActions() {
    const toggleBtn = document.getElementById('jom-toggle-refresh');
    const refreshBtn = document.getElementById('jom-refresh-now');
    const collapseBtn = document.getElementById('jom-toggle-collapse');
    if (toggleBtn) toggleBtn.addEventListener('click', () => { setPaused(!isPaused()); updateBadge(); });
    if (refreshBtn) refreshBtn.addEventListener('click', refreshNow);
    if (collapseBtn) collapseBtn.addEventListener('click', () => { setCollapsed(!isCollapsed()); applyCollapsedState(); });
  }

  function start() {
    ensureBadge();
    wireActions();
    updateBadge();
    pollSourceState();
    pollRuntimeData();
    setInterval(tick, 1000);
    setInterval(pollSourceState, STATUS_POLL_SECONDS * 1000);
    setInterval(pollRuntimeData, DATA_POLL_SECONDS * 1000);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start, { once: true });
  } else {
    start();
  }
})();

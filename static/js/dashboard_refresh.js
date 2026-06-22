
(() => {
  const REFRESH_SECONDS = 600;
  const STATUS_POLL_SECONDS = 60;
  const DATA_POLL_SECONDS = 60;
  const STORAGE_KEY_PAUSED = 'jom.autoRefreshPaused';
  const STORAGE_KEY_COLLAPSED = 'jom.autoRefreshCollapsed';
  const state = {
    countdown: REFRESH_SECONDS,
    sourceMode: 'runtime',
    sourceError: null,
    sitesCount: null,
    health: 'healthy',
    healthLabel: 'Healthy',
    lastCheck: null,
    insights: [],
    lastSyncTime: null,
    lastSyncAgeSeconds: null,
    autoSyncActive: false,
    anchorsToday: { morning: false, evening: false },
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
  function formatAge(seconds) {
    if (seconds === null || seconds === undefined) return 'never';
    if (seconds < 60) return `${seconds}s ago`;
    const mins = Math.floor(seconds / 60);
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  }

  function ensureStyles() {
    if (document.getElementById('jom-runtime-alert-styles')) return;
    const style = document.createElement('style');
    style.id = 'jom-runtime-alert-styles';
    style.textContent = `
      #jom-auto-refresh-badge {
        position: fixed;
        right: 16px;
        bottom: 16px;
        z-index: 9999;
        width: 292px;
        max-width: calc(100vw - 24px);
        border: 1px solid rgba(83,182,255,0.26);
        border-radius: 20px;
        background: linear-gradient(180deg, rgba(10,20,48,0.94), rgba(8,17,40,0.92));
        color: #eef5ff;
        backdrop-filter: blur(22px);
        box-shadow:
          0 18px 40px rgba(0,0,0,0.42),
          0 0 24px rgba(83,182,255,0.12),
          inset 0 1px 0 rgba(255,255,255,0.05);
        font: 12px/1.35 system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
        overflow: hidden;
        transition: transform 180ms ease, box-shadow 180ms ease, border-color 180ms ease;
      }
      html[data-theme="light"] #jom-auto-refresh-badge {
        background: rgba(255,255,255,0.96);
        color: #13233d;
        border-color: rgba(46,121,199,0.24);
        box-shadow:
          0 20px 38px rgba(15,23,42,0.14),
          0 0 18px rgba(46,121,199,0.10),
          inset 0 1px 0 rgba(255,255,255,0.96);
      }
      #jom-auto-refresh-badge * { box-sizing: border-box; }
      #jom-auto-refresh-badge.jom-healthy {
        border-color: rgba(57,218,149,0.34);
      }
      #jom-auto-refresh-badge.jom-warning {
        border-color: rgba(255,190,89,0.40);
        box-shadow:
          0 18px 40px rgba(0,0,0,0.44),
          0 0 34px rgba(255,190,89,0.20);
      }
      #jom-auto-refresh-badge.jom-critical {
        border-color: rgba(255,100,130,0.44);
        box-shadow:
          0 18px 40px rgba(0,0,0,0.46),
          0 0 38px rgba(255,100,130,0.24);
      }
      #jom-auto-refresh-badge.jom-collapsed {
        width: auto;
        min-width: 188px;
      }
      #jom-auto-refresh-badge .jom-head {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 8px;
        padding: 12px 12px 10px;
        border-bottom: 1px solid rgba(255,255,255,0.05);
        background: linear-gradient(90deg, rgba(83,182,255,0.10), rgba(139,92,246,0.06));
      }
      html[data-theme="light"] #jom-auto-refresh-badge .jom-head {
        border-bottom-color: rgba(46,121,199,0.10);
        background: linear-gradient(90deg, rgba(0,229,255,0.08), rgba(139,92,246,0.05));
      }
      #jom-auto-refresh-badge .jom-title {
        display: flex;
        align-items: center;
        gap: 8px;
        font-weight: 800;
        letter-spacing: 0.06em;
        text-transform: uppercase;
      }
      #jom-auto-refresh-badge .jom-subtitle {
        display: block;
        color: #95a8c8;
        font-size: 10px;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        margin-top: 2px;
      }
      html[data-theme="light"] #jom-auto-refresh-badge .jom-subtitle {
        color: #6a7d96;
      }
      #jom-auto-refresh-badge .jom-dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        background: #39da95;
        box-shadow: 0 0 0 3px rgba(57,218,149,0.24), 0 0 10px rgba(57,218,149,0.28);
      }
      #jom-auto-refresh-badge .jom-dot.warn {
        background: #ffbe59;
        box-shadow: 0 0 0 3px rgba(255,190,89,0.26), 0 0 12px rgba(255,190,89,0.30);
      }
      #jom-auto-refresh-badge .jom-dot.error {
        background: #ff6482;
        box-shadow: 0 0 0 3px rgba(255,100,130,0.28), 0 0 14px rgba(255,100,130,0.34);
      }
      #jom-auto-refresh-badge .jom-meta {
        display: flex;
        align-items: center;
        gap: 6px;
        color: #aeb8c9;
      }
      html[data-theme="light"] #jom-auto-refresh-badge .jom-meta {
        color: #5d6d85;
      }
      #jom-auto-refresh-badge .jom-mini-btn,
      #jom-auto-refresh-badge .jom-btn {
        appearance: none;
        border: 1px solid rgba(83,182,255,0.20);
        background: rgba(255,255,255,0.04);
        color: inherit;
        cursor: pointer;
        font: inherit;
      }
      html[data-theme="light"] #jom-auto-refresh-badge .jom-mini-btn,
      html[data-theme="light"] #jom-auto-refresh-badge .jom-btn {
        background: rgba(46,121,199,0.05);
      }
      #jom-auto-refresh-badge .jom-mini-btn { border-radius: 10px; padding: 4px 7px; }
      #jom-auto-refresh-badge .jom-mini-btn:hover,
      #jom-auto-refresh-badge .jom-btn:hover { background: rgba(83,182,255,0.10); }
      #jom-auto-refresh-badge .jom-body {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px;
        padding: 0 12px 10px;
      }
      #jom-auto-refresh-badge .jom-card {
        border: 1px solid rgba(83,182,255,0.14);
        border-radius: 12px;
        padding: 9px 10px;
        background: rgba(255,255,255,0.03);
        min-height: 58px;
      }
      html[data-theme="light"] #jom-auto-refresh-badge .jom-card {
        background: rgba(255,255,255,0.76);
      }
      #jom-auto-refresh-badge .jom-label {
        color: #98a5bb;
        font-size: 10px;
        text-transform: uppercase;
        letter-spacing: 0.48px;
        margin-bottom: 4px;
      }
      html[data-theme="light"] #jom-auto-refresh-badge .jom-label {
        color: #6b7a94;
      }
      #jom-auto-refresh-badge .jom-value {
        font-weight: 800;
        word-break: break-word;
      }
      #jom-auto-refresh-badge .jom-actions {
        display: flex;
        gap: 8px;
        padding: 0 12px 10px;
      }
      #jom-auto-refresh-badge .jom-btn { border-radius: 10px; padding: 7px 10px; }
      #jom-auto-refresh-badge .jom-footer {
        padding: 0 12px 12px;
        color: #96a2b8;
        font-size: 11px;
      }
      html[data-theme="light"] #jom-auto-refresh-badge .jom-footer {
        color: #5d6d85;
      }
      #jom-auto-refresh-badge .jom-insights {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        padding: 0 12px 10px;
      }
      #jom-auto-refresh-badge .jom-pill {
        border-radius: 999px;
        padding: 4px 8px;
        background: rgba(255,255,255,0.06);
        border: 1px solid rgba(83,182,255,0.14);
        color: inherit;
        font-size: 11px;
      }
      #jom-auto-refresh-badge .jom-automation-status {
        border-top: 1px solid rgba(255,255,255,0.05);
        margin-top: 10px;
        padding-top: 10px;
      }
      html[data-theme="light"] #jom-auto-refresh-badge .jom-automation-status {
        border-top-color: rgba(46,121,199,0.10);
      }
      #jom-auto-refresh-badge .jom-hidden { display: none !important; }
      @media (max-width: 640px) {
        #jom-auto-refresh-badge {
          width: calc(100vw - 20px);
          right: 10px;
          bottom: 10px;
        }
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
        <div>
          <div class="jom-title"><span class="jom-dot" id="jom-refresh-dot"></span><span>Live Runtime</span></div>
          <span class="jom-subtitle">Command Telemetry</span>
        </div>
        <div class="jom-meta"><span id="jom-runtime-mode">runtime</span><button class="jom-mini-btn" id="jom-toggle-collapse" type="button">Collapse</button></div>
      </div>
      <div id="jom-detail-wrap">
        <div class="jom-body">
          <div class="jom-card"><div class="jom-label">Next refresh</div><div class="jom-value" id="jom-countdown">10:00</div></div>
          <div class="jom-card"><div class="jom-label">Health</div><div class="jom-value" id="jom-source-status">Healthy</div></div>
        </div>
        <div class="jom-insights" id="jom-insights"></div>
        <div class="jom-body jom-automation-status">
          <div class="jom-card"><div class="jom-label">Last sync</div><div class="jom-value" id="jom-last-sync">—</div></div>
          <div class="jom-card"><div class="jom-label">Auto sync</div><div class="jom-value" id="jom-auto-status">—</div></div>
          <div class="jom-card"><div class="jom-label">Today</div><div class="jom-value" id="jom-anchors-today">—</div></div>
        </div>
        <div class="jom-actions">
          <button class="jom-btn" id="jom-toggle-refresh" type="button">Pause refresh</button>
          <button class="jom-btn" id="jom-refresh-now" type="button">Refresh now</button>
        </div>
        <div class="jom-footer" id="jom-footer-text">Auto-refresh armed for a full page reload every 600 seconds.</div>
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
    const estate = data?.estate || {};
    const summary = data?.intelligence_summary || data?.intelligence || {};
    const topRisks = Array.isArray(summary?.top_risks) ? summary.top_risks : [];
    const insights = [];
    if ((estate.managed_disabled_accounts || 0) > 0) insights.push(`${estate.managed_disabled_accounts} disabled accounts`);
    if ((estate.mfa_disabled_accounts || 0) > 0) insights.push(`${estate.mfa_disabled_accounts} MFA disabled`);
    if ((estate.not_in_userbase_count || 0) > 0) insights.push(`${estate.not_in_userbase_count} not in userbase`);
    if (criticalSites > 0) insights.push(`${criticalSites} critical site${criticalSites === 1 ? '' : 's'}`);
    if (warningSites > 0) insights.push(`${warningSites} warning site${warningSites === 1 ? '' : 's'}`);
    if (topRisks.length > 0) insights.push(`${topRisks.length} intelligence risk${topRisks.length === 1 ? '' : 's'}`);
    if ((estate.managed_disabled_accounts || 0) > 0 || criticalSites > 0) return { level: 'critical', label: 'Critical attention', insights };
    if ((estate.mfa_disabled_accounts || 0) > 0 || (estate.not_in_userbase_count || 0) > 0 || warningSites > 0 || topRisks.length > 0) return { level: 'warning', label: 'Warning attention', insights };
    return { level: 'healthy', label: 'Healthy', insights: insights.length ? insights : ['No active runtime alerts'] };
  }

  function updateInsights() {
    const wrap = document.getElementById('jom-insights');
    if (!wrap) return;
    wrap.innerHTML = '';
    const items = state.insights && state.insights.length ? state.insights : [`State: ${state.healthLabel}`];
    for (const item of items.slice(0, 3)) {
      const pill = document.createElement('span');
      pill.className = 'jom-pill';
      pill.textContent = item;
      wrap.appendChild(pill);
    }
  }

  function updateBadge() {
    const sourceStatus = document.getElementById('jom-source-status');
    const countdown = document.getElementById('jom-countdown');
    const runtimeMode = document.getElementById('jom-runtime-mode');
    const footer = document.getElementById('jom-footer-text');
    const toggleBtn = document.getElementById('jom-toggle-refresh');
    if (!sourceStatus || !countdown || !runtimeMode || !footer || !toggleBtn) return;
    runtimeMode.textContent = asText(state.sourceMode, 'runtime');
    sourceStatus.textContent = state.sourceError ? 'Error' : state.healthLabel;
    countdown.textContent = formatCountdown(state.countdown);
    toggleBtn.textContent = isPaused() ? 'Resume refresh' : 'Pause refresh';
    footer.textContent = isPaused() ? 'Auto-refresh paused in this browser. Backend loop can keep running.' : 'Auto-refresh armed for a full page reload every 600 seconds.';
    setHealthClass();
    updateInsights();
    applyCollapsedState();

    const lastSyncEl = document.getElementById('jom-last-sync');
    if (lastSyncEl) {
      lastSyncEl.textContent = formatAge(state.lastSyncAgeSeconds);
    }
    const autoStatusEl = document.getElementById('jom-auto-status');
    if (autoStatusEl) {
      autoStatusEl.textContent = state.autoSyncActive ? '✅ Active' : '⚠️ Stale';
      autoStatusEl.style.color = state.autoSyncActive ? '#39da95' : '#ffbe59';
    }
    const anchorsEl = document.getElementById('jom-anchors-today');
    if (anchorsEl) {
      const morning = state.anchorsToday.morning ? '🌅⚓' : '🌅⏳';
      const evening = state.anchorsToday.evening ? '🌇⚓' : '🌇⏳';
      anchorsEl.textContent = morning + '  ' + evening;
    }
  }

  async function pollSourceState() {
    try {
      const response = await fetch('/api/source-state', { cache: 'no-store', credentials: 'same-origin' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      state.sourceMode = data.source_mode || 'runtime';
      state.sourceError = data.source_error || null;
      state.sitesCount = data.sites_count ?? null;
      state.lastSyncTime = data.last_sync_time || null;
      state.lastSyncAgeSeconds = data.last_sync_age_seconds ?? null;
      state.autoSyncActive = data.auto_sync_active === true;
      state.anchorsToday = data.anchors_today || { morning: false, evening: false };
      updateBadge();
    } catch (error) {
      state.sourceError = error && error.message ? error.message : String(error);
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

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, { once: true });
  else start();
})();

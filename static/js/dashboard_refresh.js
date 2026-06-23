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
    health: 'healthy',
    healthLabel: 'STABLE',
    insights: [],
    autoSyncActive: false,
    anchorsToday: { morning: false, evening: false },
  };

  function isPaused() { return localStorage.getItem(STORAGE_KEY_PAUSED) === '1'; }
  function setPaused(value) { localStorage.setItem(STORAGE_KEY_PAUSED, value ? '1' : '0'); }
  function isCollapsed() { return localStorage.getItem(STORAGE_KEY_COLLAPSED) === '1'; }
  function setCollapsed(value) { localStorage.setItem(STORAGE_KEY_COLLAPSED, value ? '1' : '0'); }
  function asText(value, fallback = '—') { return (value === null || value === undefined || value === '') ? fallback : String(value); }

  function ensureStyles() {
    if (document.getElementById('jom-runtime-alert-styles')) return;
    const style = document.createElement('style');
    style.id = 'jom-runtime-alert-styles';
    style.textContent = `
      #jom-auto-refresh-badge {
        position: fixed;
        right: 12px;
        bottom: 12px;
        z-index: 9999;
        width: 220px;
        max-width: calc(100vw - 20px);
        border: 1px solid rgba(90,194,255,0.20);
        border-radius: 20px;
        background: linear-gradient(180deg, rgba(8,17,40,0.94), rgba(6,12,31,0.92));
        color: #eef5ff;
        backdrop-filter: blur(22px);
        box-shadow: 0 14px 28px rgba(0,0,0,0.34), 0 0 16px rgba(90,194,255,0.08), inset 0 1px 0 rgba(255,255,255,0.05);
        font: 12px/1.34 system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
        overflow: hidden;
        opacity: 0.96;
      }
     
      html[data-theme="light"] #jom-auto-refresh-badge {
        background: rgba(255,255,255,0.95);
        color: #13233d;
        border-color: rgba(46,121,199,0.18);
        box-shadow: 0 14px 26px rgba(15,23,42,0.12), 0 0 10px rgba(46,121,199,0.06), inset 0 1px 0 rgba(255,255,255,0.98);
      }

      #jom-auto-refresh-badge * { box-sizing: border-box; }
      
      #jom-auto-refresh-badge.jom-healthy {
        border-color: rgba(0,255,136,0.28);
      }

      #jom-auto-refresh-badge.jom-warning {
        border-color: rgba(255,179,0,0.34);
        box-shadow: 0 14px 28px rgba(0,0,0,0.36), 0 0 18px rgba(255,179,0,0.12);
      }

      #jom-auto-refresh-badge.jom-critical {
        border-color: rgba(255,0,51,0.38);
        box-shadow: 0 14px 28px rgba(0,0,0,0.38), 0 0 20px rgba(255,0,51,0.14);
      }

      #jom-auto-refresh-badge.jom-collapsed { width: auto; min-width: 180px; }
      
      #jom-auto-refresh-badge .jom-head {
        display: flex; align-items: flex-start; justify-content: space-between; gap: 8px;
        padding: 10px 10px 8px;
        border-bottom: 1px solid rgba(255,255,255,0.05);
        background: linear-gradient(90deg, rgba(90,194,255,0.08), rgba(139,92,246,0.05));
      }

      html[data-theme="light"] #jom-auto-refresh-badge .jom-head {
        border-bottom-color: rgba(46,121,199,0.10);
        background: linear-gradient(90deg, rgba(0,229,255,0.08), rgba(139,92,246,0.05));
      }
      #jom-auto-refresh-badge .jom-title {
        display: flex; align-items: center; gap: 8px; font-weight: 800; letter-spacing: 0.06em; text-transform: uppercase;
      }
      #jom-auto-refresh-badge .jom-subtitle {
        display: block; color: #95a8c8; font-size: 10px; letter-spacing: 0.12em; text-transform: uppercase; margin-top: 2px;
      }
      html[data-theme="light"] #jom-auto-refresh-badge .jom-subtitle { color: #6a7d96; }
      #jom-auto-refresh-badge .jom-dot {
        width: 10px; height: 10px; border-radius: 50%; background: #00ff88;
        box-shadow: 0 0 5px currentColor, 0 0 10px currentColor, 0 0 20px currentColor, 0 0 40px currentColor;
      }
      #jom-auto-refresh-badge .jom-dot.warn { background: #ffb300; color:#ffb300; }
      #jom-auto-refresh-badge .jom-dot.error { background: #ff0033; color:#ff0033; }
      #jom-auto-refresh-badge .jom-meta { display: flex; align-items: center; gap: 6px; color: #aeb8c9; }
      html[data-theme="light"] #jom-auto-refresh-badge .jom-meta { color: #5d6d85; }
      #jom-auto-refresh-badge .jom-mini-btn, #jom-auto-refresh-badge .jom-btn {
        appearance: none; border: 1px solid rgba(90,194,255,0.18); background: rgba(255,255,255,0.04); color: inherit; cursor: pointer; font: inherit;
      }
      #jom-auto-refresh-badge .jom-mini-btn { border-radius: 10px; padding: 4px 7px; }
      #jom-auto-refresh-badge .jom-mini-btn:hover, #jom-auto-refresh-badge .jom-btn:hover { background: rgba(90,194,255,0.10); }
      #jom-auto-refresh-badge .jom-insights { display: flex; flex-wrap: wrap; gap: 6px; padding: 10px 12px 8px; }
      #jom-auto-refresh-badge .jom-pill {
        border-radius: 999px; padding: 4px 8px; background: rgba(255,255,255,0.05); border: 1px solid rgba(90,194,255,0.10); color: inherit; font-size: 11px;
      }
      #jom-auto-refresh-badge .jom-body { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; padding: 0 10px 8px; }
      #jom-auto-refresh-badge .jom-card {
        border: 1px solid rgba(90,194,255,0.08); border-radius: 12px; padding: 9px 10px; background: rgba(255,255,255,0.02); min-height: 58px;
      }
      html[data-theme="light"] #jom-auto-refresh-badge .jom-card { background: rgba(255,255,255,0.70); }
      #jom-auto-refresh-badge .jom-label { color: #98a5bb; font-size: 10px; text-transform: uppercase; letter-spacing: 0.48px; margin-bottom: 4px; }
      html[data-theme="light"] #jom-auto-refresh-badge .jom-label { color: #6b7a94; }
      #jom-auto-refresh-badge .jom-value { font-weight: 800; word-break: break-word; }
      #jom-auto-refresh-badge .jom-actions { display: flex; gap: 6px; padding: 0 10px 8px; }

      #jom-auto-refresh-badge .jom-btn { border-radius: 10px; padding: 7px 10px; }
      #jom-auto-refresh-badge .jom-footer { padding: 0 10px 10px; color: #96a2b8; font-size: 10px; }
      html[data-theme="light"] #jom-auto-refresh-badge .jom-footer { color: #5d6d85; }
      #jom-auto-refresh-badge .jom-hidden { display: none !important; }
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
        <div>
          <div class="jom-title"><span class="jom-dot" id="jom-refresh-dot"></span><span>Live Runtime</span></div>
          <span class="jom-subtitle">Command link</span>
        </div>
        <div class="jom-meta"><span id="jom-runtime-mode">runtime</span><button class="jom-mini-btn" id="jom-toggle-collapse" type="button">Collapse</button></div>
      </div>
      <div id="jom-detail-wrap">
        <div class="jom-insights" id="jom-insights"></div>
        <div class="jom-body">
          <div class="jom-card"><div class="jom-label">Runtime state</div><div class="jom-value" id="jom-runtime-state">STABLE</div></div>
          <div class="jom-card"><div class="jom-label">Today</div><div class="jom-value" id="jom-anchors-today">—</div></div>
        </div>
        <div class="jom-actions">
          <button class="jom-btn" id="jom-toggle-refresh" type="button">Pause refresh</button>
          <button class="jom-btn" id="jom-refresh-now" type="button">Refresh now</button>
        </div>
        <div class="jom-footer" id="jom-footer-text">Runtime link active.</div>
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
    if (state.sourceError) return { level: 'critical', label: 'CRITICAL', insights: ['Source-state error detected'] };
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
    if ((estate.managed_disabled_accounts || 0) > 0 || criticalSites > 0) return { level: 'critical', label: 'CRITICAL', insights };
    if ((estate.mfa_disabled_accounts || 0) > 0 || (estate.not_in_userbase_count || 0) > 0 || warningSites > 0 || topRisks.length > 0) return { level: 'warning', label: 'WARNING', insights };
    return { level: 'healthy', label: 'STABLE', insights: insights.length ? insights : [] };
  }

  function updateInsights() {
    const wrap = document.getElementById('jom-insights');
    if (!wrap) return;
    wrap.innerHTML = '';
    const items = state.insights && state.insights.length ? state.insights : [];
    if (!items.length) {
      wrap.style.display = 'none';
      return;
    }
    wrap.style.display = 'flex';
    for (const item of items.slice(0, 3)) {
      const pill = document.createElement('span');
      pill.className = 'jom-pill';
      pill.textContent = item;
      wrap.appendChild(pill);
    }
  }

  function applyCommandCoreState(level, label) {
    const core = document.getElementById('hero-command-core');
    const stateValue = document.getElementById('hero-core-state');
    const postureValue = document.getElementById('operational-posture-value');
    const postureCard = document.getElementById('operational-posture-card');
    const runtimeState = document.getElementById('jom-runtime-state');
    if (core) {
      core.classList.remove('command-core--healthy', 'command-core--warning', 'command-core--critical');
      core.classList.add(`command-core--${level}`);
    }
    if (stateValue) stateValue.textContent = label;
    if (postureValue) postureValue.textContent = label;
    if (runtimeState) runtimeState.textContent = label;
    if (postureCard) {
      postureCard.classList.remove('status-tile--stable', 'status-tile--warning', 'status-tile--critical', 'signal-border--warning', 'signal-border--critical');
      if (level === 'critical') {
        postureCard.classList.add('status-tile--critical', 'signal-border--critical');
      } else if (level === 'warning') {
        postureCard.classList.add('status-tile--warning', 'signal-border--warning');
      } else {
        postureCard.classList.add('status-tile--stable');
      }
    }
  }

  function updateBadge() {
    const runtimeMode = document.getElementById('jom-runtime-mode');
    const footer = document.getElementById('jom-footer-text');
    const toggleBtn = document.getElementById('jom-toggle-refresh');
    if (!runtimeMode || !footer || !toggleBtn) return;
    runtimeMode.textContent = asText(state.sourceMode, 'runtime');
    toggleBtn.textContent = isPaused() ? 'Resume refresh' : 'Pause refresh';
    footer.textContent = isPaused() ? 'Runtime link paused in this browser.' : 'Runtime link active.';
    setHealthClass();
    updateInsights();
    applyCollapsedState();
    applyCommandCoreState(state.health, state.healthLabel);

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
      state.autoSyncActive = data.auto_sync_active === true;
      state.anchorsToday = data.anchors_today || { morning: false, evening: false };
      updateBadge();
    } catch (error) {
      state.sourceError = error && error.message ? error.message : String(error);
      state.health = 'critical';
      state.healthLabel = 'CRITICAL';
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
      state.healthLabel = 'WARNING';
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

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, { once: true });
  else start();
})();

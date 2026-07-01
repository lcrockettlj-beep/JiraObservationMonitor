/*
 * JOM OPERATOR DASHBOARD PAYLOAD ADAPTER EXECUTION PACK v1
 * Scope: dashboard_refresh.js source-state and dashboard data path.
 * Behaviour: prefer operator summary/surface payloads and reshape to current UI-safe object.
 * Fallback: /api/source-state and /api/data retained.
 * UI/CSS/templates: unchanged.
 */
async function jomDashboardOperatorSummaryPayloadV1() {
  var response = await fetch('/operator/summary', { cache: 'no-store', credentials: 'same-origin' });
  if (!response.ok) { throw new Error('operator summary unavailable'); }
  return await response.json();
}

async function jomDashboardOperatorSurfacePayloadV1() {
  var response = await fetch('/operator/surface', { cache: 'no-store', credentials: 'same-origin' });
  if (!response.ok) { throw new Error('operator surface unavailable'); }
  return await response.json();
}

function jomDashboardBuildSourceStateV1(summary, surface) {
  return {
    schema: 'jom-dashboard-source-state-adapter-v1',
    operator_summary: summary || {},
    runtime_status: (summary && summary.runtime) || (surface && surface.runtime) || {},
    source_freshness: (surface && surface.sources && surface.sources.freshness) || {},
    source_reliability: (surface && surface.sources && surface.sources.reliability) || {},
    operator_surface: surface || {}
  };
}

function jomDashboardBuildDataPayloadV1(summary, surface) {
  return {
    schema: 'jom-dashboard-data-adapter-v1',
    operator_summary: summary || {},
    operator_surface: surface || {},
    site_registry: (surface && surface.registry) || {},
    estate: (surface && surface.estate) || {},
    alerts: (surface && surface.alerts) || (summary && summary.top_alerts) || [],
    alert_summary: (surface && surface.alert_summary) || (summary && summary.alert_summary) || {},
    admin: (surface && surface.admin) || {},
    runtime: (surface && surface.runtime) || (summary && summary.runtime) || {}
  };
}

async function jomDashboardSourceStateAdapterV1(options) {
  try {
    var summary = await jomDashboardOperatorSummaryPayloadV1();
    var surface = await jomDashboardOperatorSurfacePayloadV1();
    var payload = jomDashboardBuildSourceStateV1(summary, surface);
    return { ok: true, status: 200, json: async function(){ return payload; } };
  } catch (error) {
    return fetch('/api/source-state', options);
  }
}

async function jomDashboardDataAdapterV1(options) {
  try {
    var summary = await jomDashboardOperatorSummaryPayloadV1();
    var surface = await jomDashboardOperatorSurfacePayloadV1();
    var payload = jomDashboardBuildDataPayloadV1(summary, surface);
    return { ok: true, status: 200, json: async function(){ return payload; } };
  } catch (error) {
    return fetch('/api/data', options);
  }
}

/*
 * JOM LEGACY JS ADAPTER MIGRATION EXECUTION PACK v1.1.1
 * Scope: dashboard_refresh.js only
 * Behaviour: operator endpoints are preflighted first, then existing compatibility routes are used for payload-shape safety.
 * UI/CSS/templates: unchanged.
 */
async function jomDashboardOperatorPreflightV111(kind) {
  if (!window.JOMOperatorAPI) { return null; }
  try {
    if (kind === 'source-state' && typeof window.JOMOperatorAPI.getOperatorSummary === 'function') {
      return await window.JOMOperatorAPI.getOperatorSummary();
    }
    if (kind === 'data' && typeof window.JOMOperatorAPI.getOperatorSurface === 'function') {
      return await window.JOMOperatorAPI.getOperatorSurface();
    }
  } catch (error) {
    return null;
  }
  return null;
}

async function jomDashboardFetchSourceStateV111(options) {
  await jomDashboardOperatorPreflightV111('source-state');
  return fetch('/api/source-state', options);
}

async function jomDashboardFetchDataV111(options) {
  await jomDashboardOperatorPreflightV111('data');
  return fetch('/api/data', options);
}

/*
 * JOM LEGACY JS ADAPTER MIGRATION EXECUTION PACK v1
 * File: static\js\dashboard_refresh.js
 * Target endpoints: /operator/summary + /operator/surface
 * Purpose: mark this module as part of the controlled legacy-to-operator adapter migration.
 * Behaviour safety: no visual, template, or CSS changes are made by this pack.
 * Compatibility routes remain active while endpoint-specific payload alignment is completed.
 */
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
    anchorsAnchors: { morning: false, evening: false },
  };

  function isPaused() { return localStorage.getItem(STORAGE_KEY_PAUSED) === '1'; }
  function setPaused(value) { localStorage.setItem(STORAGE_KEY_PAUSED, value ? '1' : '0'); }
  function isCollapsed() { return localStorage.getItem(STORAGE_KEY_COLLAPSED) === '1'; }
  function setCollapsed(value) { localStorage.setItem(STORAGE_KEY_COLLAPSED, value ? '1' : '0'); }
  function asText(value, fallback = 'ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â') { return (value === null || value === undefined || value === '') ? fallback : String(value); }

  function ensureStyles() {
    if (document.getElementById('jom-runtime-alert-styles')) return;

    const style = document.createElement('style');
    style.id = 'jom-runtime-alert-styles';
    style.textContent = `
      #jom-auto-refresh-badge {
        --jom-bg: linear-gradient(180deg, rgba(8,17,40,0.94), rgba(6,12,31,0.92));
        --jom-border: rgba(90,194,255,0.20);
        --jom-border-strong: rgba(90,194,255,0.34);
        --jom-glow: rgba(90,194,255,0.08);
        --jom-text: #eef5ff;
        --jom-muted: #95a8c8;
        --jom-subtle-bg: rgba(255,255,255,0.04);
        --jom-card-bg: rgba(255,255,255,0.03);
        --jom-head-bg: linear-gradient(90deg, rgba(90,194,255,0.10), rgba(139,92,246,0.06));
        --jom-pill-border: rgba(90,194,255,0.14);
        --jom-pill-bg: rgba(255,255,255,0.05);
        --jom-button-bg: rgba(255,255,255,0.04);
        --jom-stable: #00ff88;
        --jom-warning: #ffb300;
        --jom-critical: #ff0033;
        position: fixed;
        right: 12px;
        bottom: 12px;
        z-index: 9999;
        width: 220px;
        max-width: calc(100vw - 20px);
        border: 1px solid var(--jom-border);
        border-radius: 20px;
        background: var(--jom-bg);
        color: var(--jom-text);
        backdrop-filter: blur(22px);
        -webkit-backdrop-filter: blur(22px);
        box-shadow:
          0 14px 28px rgba(0,0,0,0.34),
          0 0 18px var(--jom-glow),
          inset 0 1px 0 rgba(255,255,255,0.06);
        font: 12px/1.34 system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
        overflow: hidden;
        opacity: 0.98;
        isolation: isolate;
      }
      #jom-auto-refresh-badge::before {
        content: "";
        position: absolute;
        inset: 0;
        background:
          radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--jom-border-strong) 34%, transparent), transparent 28%),
          radial-gradient(circle at 100% 0%, color-mix(in srgb, var(--jom-glow) 74%, transparent), transparent 24%);
        pointer-events: none;
        z-index: 0;
      }
      #jom-auto-refresh-badge * { box-sizing: border-box; }
      #jom-auto-refresh-badge > * { position: relative; z-index: 1; }

      html[data-mode="dark"] #jom-auto-refresh-badge,
      html:not([data-mode]) #jom-auto-refresh-badge {
        --jom-bg: linear-gradient(180deg, rgba(8,17,40,0.95), rgba(6,12,31,0.93));
        --jom-border: rgba(90,194,255,0.20);
        --jom-border-strong: rgba(90,194,255,0.34);
        --jom-glow: rgba(90,194,255,0.10);
        --jom-text: #eef5ff;
        --jom-muted: #95a8c8;
        --jom-subtle-bg: rgba(255,255,255,0.04);
        --jom-card-bg: rgba(255,255,255,0.03);
        --jom-head-bg: linear-gradient(90deg, rgba(90,194,255,0.10), rgba(139,92,246,0.06));
        --jom-pill-border: rgba(90,194,255,0.14);
        --jom-pill-bg: rgba(255,255,255,0.05);
        --jom-button-bg: rgba(255,255,255,0.04);
        --jom-stable: #00ff88;
        --jom-warning: #ffb300;
        --jom-critical: #ff0033;
      }
      html[data-mode="cyber"] #jom-auto-refresh-badge,
      html[data-theme="cyber"] #jom-auto-refresh-badge {
        --jom-bg: linear-gradient(180deg, rgba(9,15,42,0.95), rgba(10,16,39,0.93));
        --jom-border: rgba(0,229,255,0.22);
        --jom-border-strong: rgba(255,77,178,0.26);
        --jom-glow: rgba(0,229,255,0.14);
        --jom-text: #f7fbff;
        --jom-muted: #abc1e0;
        --jom-subtle-bg: rgba(255,255,255,0.03);
        --jom-card-bg: rgba(255,255,255,0.025);
        --jom-head-bg: linear-gradient(90deg, rgba(0,229,255,0.12), rgba(255,77,178,0.08));
        --jom-pill-border: rgba(0,229,255,0.16);
        --jom-pill-bg: rgba(0,229,255,0.06);
        --jom-button-bg: rgba(255,255,255,0.03);
        --jom-stable: #00ff96;
        --jom-warning: #ffc022;
        --jom-critical: #ff3f67;
      }
      html[data-mode="enterprise"] #jom-auto-refresh-badge,
      html[data-theme="enterprise"] #jom-auto-refresh-badge {
        --jom-bg: linear-gradient(180deg, rgba(20,29,44,0.95), rgba(15,23,35,0.93));
        --jom-border: rgba(118,152,194,0.18);
        --jom-border-strong: rgba(179,132,175,0.18);
        --jom-glow: rgba(118,152,194,0.08);
        --jom-text: #f2f6fb;
        --jom-muted: #acb8c8;
        --jom-subtle-bg: rgba(255,255,255,0.03);
        --jom-card-bg: rgba(255,255,255,0.025);
        --jom-head-bg: linear-gradient(90deg, rgba(118,152,194,0.09), rgba(179,132,175,0.05));
        --jom-pill-border: rgba(118,152,194,0.14);
        --jom-pill-bg: rgba(255,255,255,0.04);
        --jom-button-bg: rgba(255,255,255,0.03);
        --jom-stable: #42bb87;
        --jom-warning: #c8a34a;
        --jom-critical: #d05f71;
      }
      html[data-mode="noc"] #jom-auto-refresh-badge,
      html[data-theme="noc"] #jom-auto-refresh-badge {
        --jom-bg: linear-gradient(180deg, rgba(14,23,18,0.95), rgba(10,16,13,0.94));
        --jom-border: rgba(103,194,164,0.20);
        --jom-border-strong: rgba(207,163,62,0.18);
        --jom-glow: rgba(103,194,164,0.12);
        --jom-text: #eff8f0;
        --jom-muted: #b7c9b8;
        --jom-subtle-bg: rgba(255,255,255,0.025);
        --jom-card-bg: rgba(255,255,255,0.02);
        --jom-head-bg: linear-gradient(90deg, rgba(103,194,164,0.12), rgba(207,163,62,0.06));
        --jom-pill-border: rgba(103,194,164,0.18);
        --jom-pill-bg: rgba(103,194,164,0.05);
        --jom-button-bg: rgba(255,255,255,0.03);
        --jom-stable: #46c97a;
        --jom-warning: #cfa33e;
        --jom-critical: #db6058;
      }
      html[data-mode="atlassian"] #jom-auto-refresh-badge,
      html[data-theme="atlassian"] #jom-auto-refresh-badge,
      html[data-mode="light"] #jom-auto-refresh-badge,
      html[data-theme="light"] #jom-auto-refresh-badge {
        --jom-bg: linear-gradient(180deg, rgba(255,255,255,0.96), rgba(244,245,247,0.93));
        --jom-border: rgba(12,102,228,0.18);
        --jom-border-strong: rgba(12,102,228,0.26);
        --jom-glow: rgba(12,102,228,0.06);
        --jom-text: #172B4D;
        --jom-muted: #5E6C84;
        --jom-subtle-bg: rgba(255,255,255,0.72);
        --jom-card-bg: rgba(255,255,255,0.74);
        --jom-head-bg: linear-gradient(90deg, rgba(222,235,255,0.92), rgba(244,245,247,0.88));
        --jom-pill-border: rgba(12,102,228,0.14);
        --jom-pill-bg: rgba(222,235,255,0.70);
        --jom-button-bg: rgba(255,255,255,0.78);
        --jom-stable: #36B37E;
        --jom-warning: #FF9F00;
        --jom-critical: #FF5630;
        border-color: rgba(12,102,228,0.18);
        box-shadow:
          0 12px 24px rgba(9,30,66,0.12),
          0 0 0 rgba(0,0,0,0),
          inset 0 1px 0 rgba(255,255,255,0.98);
      }

      #jom-auto-refresh-badge.jom-healthy {
        border-color: color-mix(in srgb, var(--jom-stable) 58%, var(--jom-border));
        box-shadow:
          0 14px 28px rgba(0,0,0,0.34),
          0 0 18px var(--jom-glow),
          0 0 18px color-mix(in srgb, var(--jom-stable) 18%, transparent),
          inset 0 1px 0 rgba(255,255,255,0.06);
      }
      #jom-auto-refresh-badge.jom-warning {
        border-color: color-mix(in srgb, var(--jom-warning) 52%, transparent);
        box-shadow:
          0 14px 28px rgba(0,0,0,0.36),
          0 0 18px color-mix(in srgb, var(--jom-warning) 18%, transparent),
          inset 0 1px 0 rgba(255,255,255,0.05);
      }
      #jom-auto-refresh-badge.jom-critical {
        border-color: color-mix(in srgb, var(--jom-critical) 58%, transparent);
        box-shadow:
          0 14px 28px rgba(0,0,0,0.38),
          0 0 20px color-mix(in srgb, var(--jom-critical) 20%, transparent),
          inset 0 1px 0 rgba(255,255,255,0.05);
      }
      #jom-auto-refresh-badge.jom-collapsed { width: auto; min-width: 180px; }

      #jom-auto-refresh-badge .jom-head {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 8px;
        padding: 10px 10px 8px;
        border-bottom: 1px solid color-mix(in srgb, var(--jom-border) 42%, transparent);
        background: var(--jom-head-bg);
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
        color: var(--jom-muted);
        font-size: 10px;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        margin-top: 2px;
      }
      #jom-auto-refresh-badge .jom-dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        background: var(--jom-stable);
        color: var(--jom-stable);
        box-shadow:
          0 0 5px currentColor,
          0 0 10px currentColor,
          0 0 20px currentColor,
          0 0 34px currentColor;
        animation: jomPulseStable 1.8s ease-in-out infinite;
      }
      #jom-auto-refresh-badge .jom-dot.warn {
        background: var(--jom-warning);
        color: var(--jom-warning);
        animation: jomPulseWarn 1.4s ease-in-out infinite;
      }
      #jom-auto-refresh-badge .jom-dot.error {
        background: var(--jom-critical);
        color: var(--jom-critical);
        animation: jomPulseError 1.1s ease-in-out infinite;
      }
      #jom-auto-refresh-badge .jom-meta {
        display: flex;
        align-items: center;
        gap: 6px;
        color: var(--jom-muted);
      }
      #jom-auto-refresh-badge .jom-mini-btn,
      #jom-auto-refresh-badge .jom-btn {
        appearance: none;
        border: 1px solid var(--jom-pill-border);
        background: var(--jom-button-bg);
        color: inherit;
        cursor: pointer;
        font: inherit;
        backdrop-filter: blur(14px);
        -webkit-backdrop-filter: blur(14px);
      }
      #jom-auto-refresh-badge .jom-mini-btn {
        border-radius: 10px;
        padding: 4px 7px;
      }
      #jom-auto-refresh-badge .jom-mini-btn:hover,
      #jom-auto-refresh-badge .jom-btn:hover {
        background: color-mix(in srgb, var(--jom-button-bg) 60%, var(--jom-border) 16%);
        border-color: var(--jom-border-strong);
      }
      #jom-auto-refresh-badge .jom-insights {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        padding: 10px 12px 8px;
      }
      #jom-auto-refresh-badge .jom-pill {
        border-radius: 999px;
        padding: 4px 8px;
        background: var(--jom-pill-bg);
        border: 1px solid var(--jom-pill-border);
        color: inherit;
        font-size: 11px;
      }
      #jom-auto-refresh-badge .jom-body {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 6px;
        padding: 0 10px 8px;
      }
      #jom-auto-refresh-badge .jom-card {
        border: 1px solid color-mix(in srgb, var(--jom-border) 34%, transparent);
        border-radius: 12px;
        padding: 9px 10px;
        background: var(--jom-card-bg);
        min-height: 58px;
      }
      #jom-auto-refresh-badge .jom-label {
        color: var(--jom-muted);
        font-size: 10px;
        text-transform: uppercase;
        letter-spacing: 0.48px;
        margin-bottom: 4px;
      }
      #jom-auto-refresh-badge .jom-value {
        font-weight: 800;
        word-break: break-word;
      }
      #jom-anchors-today {
        font-size: 11px;
        letter-spacing: 0.04em;
        white-space: nowrap;
      }
      #jom-auto-refresh-badge .jom-actions {
        display: flex;
        gap: 6px;
        padding: 0 10px 8px;
      }
      #jom-auto-refresh-badge .jom-btn {
        border-radius: 10px;
        padding: 7px 10px;
      }
      #jom-auto-refresh-badge .jom-footer {
        padding: 0 10px 10px;
        color: var(--jom-muted);
        font-size: 10px;
      }
      #jom-auto-refresh-badge .jom-hidden { display: none !important; }

      @keyframes jomPulseStable {
        0%, 100% { opacity: 0.88; transform: scale(1); filter: saturate(100%); }
        50% { opacity: 1; transform: scale(1.08); filter: saturate(132%); }
      }
      @keyframes jomPulseWarn {
        0%, 100% { opacity: 0.84; transform: scale(1); }
        50% { opacity: 1; transform: scale(1.10); }
      }
      @keyframes jomPulseError {
        0%, 100% { opacity: 0.82; transform: scale(1); }
        50% { opacity: 1; transform: scale(1.12); }
      }

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
          <span class="jom-subtitle">State link</span>
        </div>
        <div class="jom-meta"><span id="jom-runtime-mode">live</span><button class="jom-mini-btn" id="jom-toggle-collapse" type="button">Collapse</button></div>
      </div>
      <div id="jom-detail-wrap">
        <div class="jom-insights" id="jom-insights"></div>
        <div class="jom-body">
          <div class="jom-card"><div class="jom-label">State</div><div class="jom-value" id="jom-runtime-state">STABLE</div></div>
          <div class="jom-card"><div class="jom-label">Anchors</div><div class="jom-value" id="jom-anchors-today">ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â</div></div>
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

    runtimeMode.textContent = 'live';
    toggleBtn.textContent = isPaused() ? 'Resume refresh' : 'Pause refresh';
    footer.textContent = isPaused() ? 'Runtime paused in this browser.' : 'Runtime link active.';
    setHealthClass();
    updateInsights();
    applyCollapsedState();
    applyCommandCoreState(state.health, state.healthLabel);

    const anchorsEl = document.getElementById('jom-anchors-today');
    if (anchorsEl) {
      const sunrise = String.fromCodePoint(0x1F305);
      const sunset = String.fromCodePoint(0x1F307);
      const anchor = String.fromCodePoint(0x2693);
      const hourglass = String.fromCodePoint(0x23F3);
      const morning = state.anchorsAnchors.morning ? (sunrise + anchor) : (sunrise + hourglass);
      const evening = state.anchorsAnchors.evening ? (sunset + anchor) : (sunset + hourglass);
      anchorsEl.textContent = morning + '  ' + evening;
    }
  }

  async function pollSourceState() {
    try {
      const response = await jomDashboardSourceStateAdapterV1({ cache: 'no-store', credentials: 'same-origin' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      state.sourceMode = data.source_mode || 'runtime';
      state.sourceError = data.source_error || null;
      state.autoSyncActive = data.auto_sync_active === true;
      state.anchorsAnchors = data.anchors_today || { morning: false, evening: false };
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
      const response = await jomDashboardDataAdapterV1({ cache: 'no-store', credentials: 'same-origin' });
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

function jomLegacyAdapterMigrationNoteV1() {
  return {
    phase: "legacy-js-adapter-migration-execution-v1",
    behaviour: "compatibility routes remain active until payload-specific adapter swaps are validated",
    uiChanges: false,
    cssChanges: false,
    templateChanges: false
  };
}



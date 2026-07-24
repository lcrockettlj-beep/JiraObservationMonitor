(() => {
  'use strict';

  const ENDPOINTS = {
    summary: '/operator/summary',
    alerts: '/operator/alerts',
    registry: '/registry/sites',
    users: '/users/footprint',
    sourceState: '/api/source-state',
    productAccess: '/estate/product-access',
    executiveReport: '/reports/generated/executive/html'
  };

  function setText(id, value) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = value === null || value === undefined || value === '' ? 'n/a' : String(value);
  }

  function unwrap(payload) {
    if (payload && typeof payload === 'object' && payload.data && typeof payload.data === 'object') {
      return payload.data;
    }
    return payload && typeof payload === 'object' ? payload : {};
  }

  function asNumber(value, fallback = null) {
    const n = Number(value);
    return Number.isFinite(n) ? n : fallback;
  }

  async function getJson(url) {
    const response = await fetch(url, { cache: 'no-store' });
    if (!response.ok) throw new Error(url + ' returned ' + response.status);
    return response.json();
  }

  async function safeJson(url, fallback = {}) {
    try { return await getJson(url); }
    catch (err) {
      console.warn('Command Centre data fetch failed', url, err);
      return fallback;
    }
  }

  function registrySummary(registryPayload) {
    const registry = unwrap(registryPayload);
    const sites = Array.isArray(registry.sites) ? registry.sites : [];
    const summary = registry.summary || {};

    const total = asNumber(summary.total_sites, sites.length || 0);
    const monitored = asNumber(
      summary.monitored_count,
      sites.filter(site => site && (site.is_monitored === true || site.classification === 'monitored')).length
    );
    const discovered = asNumber(
      summary.discovered_count,
      sites.filter(site => site && site.classification === 'discovered').length
    );
    const pending = asNumber(
      summary.pending_onboarding_count,
      sites.filter(site => site && String(site.collector_onboarding_status || '').toLowerCase().includes('pending')).length
    );

    return { total, monitored, discovered, pending, sites };
  }

  function deriveProductAccessUsers(sourceStatePayload, productAccessPayload) {
    const sourceState = unwrap(sourceStatePayload);
    const productAccess = unwrap(productAccessPayload);

    const liveProduct = sourceState.live_product_access || {};
    const liveTotal = asNumber(liveProduct.total_jira_product_user_count);
    if (liveTotal !== null) return liveTotal;

    const productSummary = productAccess.summary || {};
    const productTotal = asNumber(productSummary.total_jira_product_user_count);
    if (productTotal !== null) return productTotal;

    const adminTruth = unwrap(sourceState.admin_truth || {});
    const liveOverlay = adminTruth.live_product_access_truth || {};
    const liveOverlaySummary = liveOverlay.summary || {};
    const overlayTotal = asNumber(liveOverlaySummary.total_jira_product_user_count);
    if (overlayTotal !== null) return overlayTotal;

    return null;
  }

  function deriveDataHealth(sourceStatePayload) {
    const sourceState = unwrap(sourceStatePayload);

    const freshnessContract = sourceState.source_freshness || {};
    const freshnessData = unwrap(freshnessContract);
    const freshnessSummary = freshnessData.summary || {};

    const reliabilityContract = sourceState.source_reliability || {};
    const reliabilityData = unwrap(reliabilityContract);
    const reliabilitySummary = reliabilityData.summary || {};

    const freshnessOverall = String(
      freshnessSummary.overall_state || freshnessData.overall_state || freshnessContract.status || ''
    ).toLowerCase();

    const reliabilityOverall = String(
      reliabilityData.overall_status || reliabilityContract.status || ''
    ).toLowerCase();

    const issueCount = asNumber(reliabilitySummary.issue_count ?? reliabilityData.summary?.issue_count, 0);

    if (freshnessOverall === 'critical' || reliabilityOverall === 'critical') return 'Critical';
    if (
      freshnessOverall === 'attention' ||
      freshnessOverall === 'stale' ||
      reliabilityOverall === 'attention' ||
      issueCount > 0
    ) return 'Review';
    if (freshnessOverall === 'ok' || freshnessOverall === 'current' || reliabilityOverall === 'ok') return 'OK';
    return 'Review';
  }

  function topAlerts(alertsPayload, summaryPayload) {
    const alerts = Array.isArray(alertsPayload.alerts) ? alertsPayload.alerts : [];
    const summary = unwrap(summaryPayload);
    const fallback = Array.isArray(summary.top_alerts) ? summary.top_alerts : [];
    return alerts.length ? alerts : fallback;
  }

  function renderActionList(alertsPayload, summaryPayload, registryPayload) {
    const list = document.getElementById('jom-final-risk-list');
    if (!list) return;

    const reg = registrySummary(registryPayload);
    const alerts = topAlerts(alertsPayload, summaryPayload).slice(0, 5);
    const rows = [];

    alerts.forEach(alert => {
      if (!alert || !alert.title) return;
      rows.push(`<li><strong>${escapeHtml(alert.title)}</strong><span>${escapeHtml(alert.reason || alert.recommended_action || 'Review required')}</span></li>`);
    });

    if (reg.discovered + reg.pending > 0) {
      rows.push(`<li><strong>Site review required</strong><span>${reg.discovered + reg.pending} site(s) awaiting review or onboarding decision.</span></li>`);
    }

    if (!rows.length) {
      rows.push('<li><strong>No immediate action required</strong><span>Live backend contracts are currently reporting no action queue.</span></li>');
    }

    list.innerHTML = rows.join('');
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function renderRail(summaryPayload, alertsPayload, registryPayload, sourceStatePayload, productAccessPayload) {
    const summary = unwrap(summaryPayload);
    const reg = registrySummary(registryPayload);
    const alerts = Array.isArray(alertsPayload.alerts) ? alertsPayload.alerts : [];
    const alertCount = asNumber(alertsPayload.count, alerts.length || asNumber(summary.alert_summary?.total, 0));
    const reviewItems = reg.discovered + reg.pending;
    const coverage = reg.total > 0 ? Math.round((reg.monitored / reg.total) * 100) : 0;
    const users = deriveProductAccessUsers(sourceStatePayload, productAccessPayload);

    setText('jom-rail-total-sites', reg.total);
    setText('jom-rail-monitored-sites', reg.monitored);
    setText('jom-rail-review-items', reviewItems);
    setText('jom-rail-data-health', deriveDataHealth(sourceStatePayload));

    setText('jom-rail-runtime', summary.runtime?.state || 'OK');
    setText('jom-rail-alerts', alertCount);
    setText('jom-rail-users', users);

    setText('jom-rail-monitoring-coverage', coverage + '%');
    setText('jom-rail-coverage-monitored', reg.monitored);
    setText('jom-rail-coverage-review', reviewItems);

    const coverageReason = document.getElementById('jom-rail-coverage-reason');
    if (coverageReason) {
      coverageReason.textContent = `${reg.monitored} monitored - ${reviewItems} awaiting review`;
    }
  }

  async function refreshCommandCentre() {
    const [summary, alerts, registry, users, sourceState, productAccess] = await Promise.all([
      safeJson(ENDPOINTS.summary),
      safeJson(ENDPOINTS.alerts),
      safeJson(ENDPOINTS.registry),
      safeJson(ENDPOINTS.users),
      safeJson(ENDPOINTS.sourceState),
      safeJson(ENDPOINTS.productAccess)
    ]);

    renderRail(summary, alerts, registry, sourceState, productAccess);
    renderActionList(alerts, summary, registry);
  }

  function run() { refreshCommandCentre(); }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', run);
  } else {
    run();
  }
})();

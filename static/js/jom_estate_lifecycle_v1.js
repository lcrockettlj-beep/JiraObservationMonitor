/* JOM Estate release frontend v1
 * Owner: static/js/jom_estate_lifecycle_v1.js
 * Contract: /api/workspace/estate
 * Rules: no static dataset path, no legacy JSON, no Command Centre contract dependency.
 */
(function () {
  'use strict';

  const CONTRACT_URL = '/api/workspace/estate';

  const asArray = value => Array.isArray(value) ? value : [];
  const asNumber = (value, fallback) => {
    const n = Number(value);
    return Number.isFinite(n) ? n : fallback;
  };
  const unwrap = payload => payload && typeof payload === 'object' && payload.data && typeof payload.data === 'object' ? payload.data : (payload || {});

  function get(obj, path, fallback) {
    let current = obj;
    for (const part of String(path || '').split('.')) {
      if (current && typeof current === 'object' && part in current) current = current[part];
      else return fallback;
    }
    return current === null || current === undefined ? fallback : current;
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function setText(id, value, state) {
    const node = document.getElementById(id);
    if (!node) return;
    node.textContent = value === null || value === undefined || value === '' ? '--' : String(value);
    if (state) node.setAttribute('data-state', state);
  }

  function normaliseState(site) {
    return String(site.lifecycle || site.classification || site.status || site.state || site.collector_onboarding_status || '').toLowerCase();
  }

  function isMonitored(site) {
    const state = normaliseState(site);
    return !!(site.is_monitored === true || site.monitored === true || site.in_monitoring_scope === true || state === 'monitored' || state.includes('monitoring_enabled') || state.includes('monitoring enabled'));
  }

  function isIgnored(site) {
    const state = normaliseState(site);
    return state.includes('ignored') || state.includes('retired');
  }

  function needsReview(site) {
    if (!site || isMonitored(site) || isIgnored(site)) return false;
    const state = normaliseState(site);
    return state === '' || state.includes('discovered') || state.includes('review') || state.includes('pending') || state.includes('gap') || state.includes('error');
  }

  function siteKey(site) {
    return String(site.site_key || site.key || site.cloud_id || site.name || site.site_name || '').trim();
  }

  function siteName(site) {
    return String(site.name || site.site_name || site.key || site.site_key || 'Unknown site');
  }

  function siteUrl(site) {
    return String(site.url || site.site_url || '').trim();
  }

  function lifecycleLabel(site) {
    if (isMonitored(site)) return 'Monitored';
    if (isIgnored(site)) return 'Ignored';
    const state = normaliseState(site);
    if (state.includes('pending')) return 'Approval Pending';
    if (state.includes('error') || state.includes('gap')) return 'Review Required';
    if (state.includes('review')) return 'Review Required';
    return 'Discovered';
  }

  function healthLabel(site) {
    if (isMonitored(site)) return 'Healthy';
    if (isIgnored(site)) return 'Ignored';
    return 'Review';
  }

  function pillClass(label) {
    const value = String(label || '').toLowerCase();
    if (value.includes('healthy') || value.includes('monitored') || value === 'ok') return 'estate-status-pill estate-status-pill--ok';
    if (value.includes('ignored') || value.includes('retired')) return 'estate-status-pill estate-status-pill--retired';
    return 'estate-status-pill estate-status-pill--review';
  }

  function sitesFromPayload(root) {
    const candidates = [
      get(root, 'registry.sites', null),
      get(root, 'site_registry.sites', null),
      get(root, 'sites', null),
      get(root, 'registry.items', null)
    ];
    for (const list of candidates) {
      if (Array.isArray(list)) return list.filter(item => item && typeof item === 'object');
    }
    return [];
  }

  function summaryFromPayload(root, sites) {
    const summary = get(root, 'registry_summary', get(root, 'registry.summary', get(root, 'summary', {}))) || {};
    const metrics = get(root, 'metrics', {}) || {};
    const total = asNumber(summary.total_sites ?? summary.site_count ?? metrics.total_sites, sites.length);
    const monitored = asNumber(summary.monitored_count ?? metrics.monitored_sites, sites.filter(isMonitored).length);
    const discovered = asNumber(summary.discovered_count ?? metrics.discovered_sites, sites.filter(needsReview).length);
    const pending = asNumber(summary.pending_onboarding_count ?? summary.pending_count ?? metrics.pending_onboarding, sites.filter(site => normaliseState(site).includes('pending')).length);
    const review = asNumber(summary.review_count ?? metrics.review_items, sites.filter(needsReview).length);
    const ignored = sites.filter(isIgnored).length;
    const coverage = total > 0 ? Math.round((monitored / total) * 100) : 0;
    return {total, monitored, discovered, pending, review, ignored, coverage};
  }

  function userCount(root) {
    const candidates = [
      get(root, 'users.metric', null),
      get(root, 'users_metric.metric', null),
      get(root, 'estate_product_access.summary.total_jira_product_user_count', null),
      get(root, 'users.summary.total_jira_product_user_count', null)
    ];
    for (const value of candidates) {
      const n = asNumber(value, null);
      if (n !== null) return n;
    }
    return null;
  }

  function renderReviewQueue(sites, summary) {
    const list = document.getElementById('estate-review-list');
    const count = document.getElementById('estate-review-count');
    const reviewSites = sites.filter(needsReview);
    setText('estate-review-count', reviewSites.length);
    if (!list) return;
    if (!reviewSites.length) {
      list.innerHTML = '<p class="estate-empty">No discovered sites currently require lifecycle review.</p>';
      return;
    }
    list.innerHTML = reviewSites.map(site => {
      const key = siteKey(site);
      const name = siteName(site);
      const reason = lifecycleLabel(site);
      const url = siteUrl(site);
      const action = url ? '<a class="estate-action-link" href="' + escapeHtml(url) + '" target="_blank" rel="noopener noreferrer">Open site</a>' : '<span class="estate-status-pill estate-status-pill--review">Review required</span>';
      return '<article class="estate-review-item">' +
        '<div><strong>' + escapeHtml(name) + '</strong><br><small>Key: ' + escapeHtml(key || 'Unavailable') + '</small><br><span>' + escapeHtml(reason) + '</span></div>' +
        action +
      '</article>';
    }).join('');
  }

  function renderRegistry(sites) {
    const body = document.getElementById('estate-registry-body');
    if (!body) return;
    if (!sites.length) {
      body.innerHTML = '<tr><td colspan="6">No site records were returned by the live Estate contract.</td></tr>';
      return;
    }
    const sorted = sites.slice().sort((a, b) => {
      const ma = isMonitored(a) ? 0 : 1;
      const mb = isMonitored(b) ? 0 : 1;
      if (ma !== mb) return ma - mb;
      return siteName(a).localeCompare(siteName(b));
    });
    body.innerHTML = sorted.map(site => {
      const key = siteKey(site);
      const name = siteName(site);
      const url = siteUrl(site);
      const lifecycle = lifecycleLabel(site);
      const monitoring = isMonitored(site) ? 'Enabled' : 'Not enabled';
      const health = healthLabel(site);
      const last = site.last_observation || site.last_seen || site.observed_at || site.updated_at || 'Live contract';
      const action = url ? '<a class="estate-site-link estate-site-link--button" href="' + escapeHtml(url) + '" target="_blank" rel="noopener noreferrer">Open site <span class="estate-external-icon">↗</span></a>' : '<span class="estate-status-pill estate-status-pill--review">No site link</span>';
      return '<tr data-site-key="' + escapeHtml(key) + '" data-estate-state="' + escapeHtml(normaliseState(site)) + '">' +
        '<td><strong>' + escapeHtml(name) + '</strong><br><small>' + escapeHtml(key || 'Unavailable') + '</small></td>' +
        '<td><span class="' + pillClass(lifecycle) + '">' + escapeHtml(lifecycle) + '</span></td>' +
        '<td><span class="' + pillClass(monitoring) + '">' + escapeHtml(monitoring) + '</span></td>' +
        '<td><span class="' + pillClass(health) + '">' + escapeHtml(health) + '</span></td>' +
        '<td>' + escapeHtml(last) + '</td>' +
        '<td>' + action + '</td>' +
      '</tr>';
    }).join('');
  }

  function updateRail(root, sites, summary) {
    setText('rail-total-sites', summary.total);
    setText('rail-monitored-sites', summary.monitored);
    setText('rail-discovered-sites', summary.discovered);
    setText('rail-review-queue', summary.review);
    setText('rail-pending-sites', summary.pending);
    setText('rail-ignored-sites', summary.ignored);
    setText('rail-registry-status', sites.length ? 'OK' : 'Review', sites.length ? 'ok' : 'review');
    setText('rail-users-count', userCount(root) === null ? '--' : userCount(root));
    setText('rail-alert-count', summary.review);
  }

  function applyFiltering() {
    const search = document.getElementById('estate-search');
    const filter = document.getElementById('estate-filter');
    const rows = Array.from(document.querySelectorAll('#estate-registry-body tr'));
    const term = String(search && search.value || '').toLowerCase();
    const mode = String(filter && filter.value || 'all').toLowerCase();
    rows.forEach(row => {
      const text = row.textContent.toLowerCase();
      const state = String(row.getAttribute('data-estate-state') || '').toLowerCase();
      let match = !term || text.includes(term);
      if (mode === 'monitored') match = match && text.includes('enabled');
      if (mode === 'discovered') match = match && !text.includes('enabled') && !state.includes('ignored');
      if (mode === 'pending') match = match && state.includes('pending');
      if (mode === 'ignored') match = match && state.includes('ignored');
      row.style.display = match ? '' : 'none';
    });
  }

  function bindFilters() {
    const search = document.getElementById('estate-search');
    const filter = document.getElementById('estate-filter');
    if (search && !search.dataset.jomBound) {
      search.dataset.jomBound = 'true';
      search.addEventListener('input', applyFiltering);
    }
    if (filter && !filter.dataset.jomBound) {
      filter.dataset.jomBound = 'true';
      filter.addEventListener('change', applyFiltering);
    }
  }

  function render(payload) {
    const root = unwrap(payload);
    const sites = sitesFromPayload(root);
    const summary = summaryFromPayload(root, sites);
    renderReviewQueue(sites, summary);
    renderRegistry(sites);
    updateRail(root, sites, summary);
    bindFilters();
  }

  function renderError(error) {
    const review = document.getElementById('estate-review-list');
    const body = document.getElementById('estate-registry-body');
    if (review) review.innerHTML = '<p class="estate-empty">Estate workspace contract could not be loaded.</p>';
    if (body) body.innerHTML = '<tr><td colspan="6">Estate workspace contract could not be loaded: ' + escapeHtml(error && error.message ? error.message : error) + '</td></tr>';
    setText('rail-registry-status', 'Review', 'review');
  }

  function loadEstate() {
    fetch(CONTRACT_URL, {cache: 'no-store', headers: {'Accept': 'application/json'}, credentials: 'same-origin'})
      .then(response => {
        if (!response.ok) throw new Error('Estate workspace contract returned HTTP ' + response.status);
        return response.json();
      })
      .then(render)
      .catch(renderError);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', loadEstate);
  else loadEstate();
}());

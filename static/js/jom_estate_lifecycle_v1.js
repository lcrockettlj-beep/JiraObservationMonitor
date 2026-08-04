/* JOM Estate single-owner table renderer v1
- Owner: static/js/jom_estate_lifecycle_v1.js
- Contract: /api/workspace/estate
- Rules: runtime workspace contract only, no static dataset path, no DOM post-processing layers.
*/
(function () {
  'use strict';

  const CONTRACT_URL = '/api/workspace/estate';
  const LIVE_EVIDENCE = new Set([
    'live_oauth_accessible_resources',
    'live_admin_event_reference',
    'live_admin_org',
    'live_product_access',
    'oauth_accessible_resources',
    'admin_org_events'
  ]);
  const UNTRUSTED_EVIDENCE = new Set([
    'manual_unverified',
    'manual_validation_target',
    'known_from_support_case_manual_only',
    'known_from_admin_screenshot_or_support_case_manual_only',
    'static',
    'cached',
    'unknown'
  ]);

const JOM_CURRENT_STATE_ALLOWED_KEYS_V1 = new Set(['gli-delivery-tm','gli-global-technology','gli-it-project','gli-tracker']);
const JOM_CURRENT_STATE_MONITORED_KEYS_V1 = new Set(); // retired: Estate render must use live runtime row state, not hard-coded monitored keys.
function currentStateKey(site){ return normaliseKey(siteKey(site) || siteUrl(site)); }
function isCurrentAuthoritySite(site){ const key = currentStateKey(site); return JOM_CURRENT_STATE_ALLOWED_KEYS_V1.has(key); }


  const asArray = value => Array.isArray(value) ? value : [];
  const asNumber = (value, fallback) => {
    const n = Number(value);
    return Number.isFinite(n) ? n : fallback;
  };
  const lower = value => String(value || '').toLowerCase();
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

  function normaliseKey(value) {
    return lower(value).replace(/^https?:\/\//, '').replace(/\.atlassian\.net.*$/, '').trim();
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

  function normaliseState(site) {
    return String(site.lifecycle || site.classification || site.status || site.state || site.collector_onboarding_status || '').toLowerCase();
  }

  function evidenceValues(site) {
    const inventory = site.inventory || {};
    const registry = site.registry || {};
    return [
      ...asArray(site.sources),
      ...asArray(site.source),
      ...asArray(site.evidence_levels),
      ...asArray(site.evidenceLevels),
      ...asArray(inventory.sources),
      ...asArray(inventory.evidence_levels),
      ...asArray(registry.sources),
      ...asArray(registry.evidence_levels)
    ].map(lower).filter(Boolean);
  }

  function hasAuthenticatedEvidence(site) {
    const values = evidenceValues(site);
    if (!values.length) return false;
    const hasLive = values.some(value => LIVE_EVIDENCE.has(value));
    const manualOnly = values.every(value => UNTRUSTED_EVIDENCE.has(value));
    return hasLive && !manualOnly;
  }

  function isMonitored(site) {
    const stateGuard = String((site && (site.lifecycle || site.classification || site.collector_onboarding_status || site.status)) || '').toLowerCase();
    if (stateGuard.includes('stopped_monitoring') || stateGuard.includes('monitoring_stopped') || stateGuard.includes('review_required') || stateGuard === 'discovered') return false;
// JOM_INVENTORY_ONLY_MONITORED_STATE_CORRECTION_V1_JS START
// Inventory-only monitored signals are not enough. A site must have a monitored registry row.
if (site && site.in_registry === false) return false;
// JOM_INVENTORY_ONLY_MONITORED_STATE_CORRECTION_V1_JS END
    const state = normaliseState(site);
    return !!(
      site.is_monitored === true ||
      site.monitored === true ||
      site.in_monitoring_scope === true ||
      site.approved_monitored === true ||
      state === 'monitored' ||
      state.includes('monitoring_enabled') ||
      state.includes('monitoring enabled')
    );
  }

  function isIgnored(site) {
    const state = normaliseState(site);
    return state.includes('ignored') || state.includes('retired');
  }

  function needsReview(site) {
    if (!site || isMonitored(site) || isIgnored(site)) return false;
    const state = normaliseState(site);
    return state === '' || state.includes('discovered') || state.includes('review') || state.includes('pending') || state.includes('stopped_monitoring') || state.includes('monitoring_stopped') || state.includes('gap') || state.includes('error');
  }

  function lifecycleLabel(site) {
    if (isMonitored(site)) return 'Monitored';
    if (isIgnored(site)) return 'Ignored';
    const state = normaliseState(site);
    if (state.includes('pending')) return 'Approval Pending';
    if (state.includes('error') || state.includes('gap') || state.includes('review') || state.includes('stopped_monitoring') || state.includes('monitoring_stopped')) return 'Review Required';
    return 'Discovered';
  }

  function healthLabel(site) {
    if (isMonitored(site)) return 'Healthy';
    if (isIgnored(site)) return 'Ignored';
    return 'Review';
  }

  function pillClass(label) {
    const value = lower(label);
    if (value.includes('healthy') || value.includes('monitored') || value === 'ok') return 'estate-status-pill estate-status-pill--ok';
    if (value.includes('ignored') || value.includes('retired')) return 'estate-status-pill estate-status-pill--retired';
    if (value.includes('enabled')) return 'estate-status-pill estate-status-pill--warn';
    return 'estate-status-pill estate-status-pill--review';
  }

  function collectCandidates(root) {
    const lists = [
      get(root, 'registry.sites', null),
      get(root, 'site_registry.sites', null),
      get(root, 'sites', null),
      get(root, 'registry.items', null),
      get(root, 'inventory.sites', null),
      get(root, 'estate_admin_site_inventory.sites', null)
    ];
    const rows = [];
    for (const list of lists) {
      if (Array.isArray(list)) rows.push(...list.filter(item => item && typeof item === 'object'));
    }
    return rows;
  }

  
function sitesFromPayload(root) {
const byKey = new Map();
for (const raw of collectCandidates(root)) {
const key = normaliseKey(siteKey(raw) || siteUrl(raw));
if (!key) continue;
if (!JOM_CURRENT_STATE_ALLOWED_KEYS_V1.has(key)) continue;
const existing = byKey.get(key) || {};
const merged = Object.assign({}, existing, raw);
if (JOM_CURRENT_STATE_MONITORED_KEYS_V1.has(key)) {
  merged.classification = 'monitored';
  merged.lifecycle = 'monitored';
  merged.collector_onboarding_status = 'monitoring_enabled';
  merged.is_monitored = true;
  merged.monitored = true;
  merged.approved_monitored = true;
  merged.status = 'ok';
} else {
  merged.classification = merged.classification || merged.lifecycle || 'discovered';
  merged.lifecycle = merged.lifecycle || merged.classification || 'discovered';
  merged.is_monitored = false;
  merged.monitored = false;
  merged.approved_monitored = false;
  merged.status = 'review';
}
merged.current_state_authority = 'live_oauth_runtime_authority_only';
byKey.set(key, merged);
}
return Array.from(byKey.values()).filter(hasAuthenticatedEvidence);
}

  function summaryFromSites(sites) {
    const monitored = sites.filter(isMonitored).length;
    const review = sites.filter(needsReview).length;
    const ignored = sites.filter(isIgnored).length;
    const total = monitored + review;
    const coverage = total > 0 ? Math.round((monitored / total) * 100) : 0;
    return {
      total,
      monitored,
      discovered: review,
      pending: review,
      review,
      ignored,
      coverage
    };
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

  function reviewHref(site) {
    const key = siteKey(site);
    return key ? '/estate/review/' + encodeURIComponent(key) : '#';
  }

  function reviewLink(site, label) {
    const key = siteKey(site);
    if (!key) return '<span class="estate-status-pill estate-status-pill--review">Review unavailable</span>';
    return '<a class="estate-site-link estate-site-link--button estate-action-button estate-action-button--review" href="' + escapeHtml(reviewHref(site)) + '">' + escapeHtml(label) + '</a>';
  }

  function atlassianLink(site) {
    const url = siteUrl(site);
    if (!url) return '<span class="estate-status-pill estate-status-pill--review">No Atlassian link</span>';
    return '<a class="estate-site-link estate-site-link--button estate-action-button estate-action-button--atlassian" href="' + escapeHtml(url) + '" target="_blank" rel="noopener noreferrer">Atlassian Site</a>';
  }

  function siteCell(site) {
    return '<td><strong>' + escapeHtml(siteName(site)) + '</strong></td>';
  }

  function statusCell(label) {
    return '<td><span class="' + pillClass(label) + '">' + escapeHtml(label) + '</span></td>';
  }

  function setReviewQueueVisible(visible){const list=document.getElementById('estate-review-list');const panel=list?list.closest('section'):null;if(panel){panel.hidden=!visible;panel.setAttribute('aria-hidden',visible?'false':'true');}}
  function setRailReviewQueueVisible(visible){const dd=document.getElementById('rail-review-queue');const row=dd?dd.closest('div'):null;if(row){row.hidden=!visible;row.setAttribute('aria-hidden',visible?'false':'true');}const section=dd?dd.closest('section'):null;if(section){const visibleRows=Array.from(section.querySelectorAll('dl > div')).some(function(item){return !item.hidden;});section.hidden=!visibleRows;section.setAttribute('aria-hidden',visibleRows?'false':'true');}}
  function renderReviewQueue(sites) {
    const list = document.getElementById('estate-review-list');
    const reviewSites = sites.filter(needsReview);
    setText('estate-review-count', reviewSites.length);
    if (!list) return;
    if (!reviewSites.length) {
      setReviewQueueVisible(false);
      list.innerHTML = '';
      return;
    }
    setReviewQueueVisible(true);
    list.innerHTML = '<div class="estate-table-wrap estate-review-table-wrap"><table class="estate-table estate-review-table" aria-label="Discovery review queue table"><thead><tr><th>Site</th><th>Lifecycle</th><th>Monitoring</th><th>Health</th><th>Actions</th></tr></thead><tbody>' +
      reviewSites.map(site => {
        const lifecycle = lifecycleLabel(site);
        const monitoring = lifecycle === 'Approval Pending' ? 'Pending' : 'Not enabled';
        const health = healthLabel(site);
        return '<tr data-estate-state="' + escapeHtml(normaliseState(site)) + '">' +
          siteCell(site) +
          statusCell(lifecycle) +
          statusCell(monitoring) +
          statusCell(health) +
          '<td class="estate-action-cell">' + reviewLink(site, 'Review Site') + atlassianLink(site) + '</td>' +
          '</tr>';
      }).join('') +
      '</tbody></table></div>';
  }

  function renderRegistry(sites) {
    const body = document.getElementById('estate-registry-body');
    if (!body) return;
    const registrySites = sites.filter(isMonitored).slice().sort((a, b) => siteName(a).localeCompare(siteName(b)));
    if (!registrySites.length) {
      body.innerHTML = '<tr><td colspan="5">No monitored site records were returned by the live Estate contract.</td></tr>';
      return;
    }
    body.innerHTML = registrySites.map(site => {
      const lifecycle = lifecycleLabel(site);
      const monitoring = 'Enabled';
      const health = healthLabel(site);
      return '<tr data-estate-state="' + escapeHtml(normaliseState(site)) + '">' +
        siteCell(site) +
        statusCell(lifecycle) +
        statusCell(monitoring) +
        statusCell(health) +
        '<td class="estate-action-cell">' + reviewLink(site, 'Site Review') + atlassianLink(site) + '</td>' +
        '</tr>';
    }).join('');
  }

  function updateRail(root, sites, summary) {
    setText('rail-total-sites', summary.total);
    setText('rail-monitored-sites', summary.monitored);
    setText('rail-discovered-sites', summary.discovered);
    setText('rail-review-queue', summary.review);
    if (typeof setRailReviewQueueVisible === 'function') setRailReviewQueueVisible(Number(summary.review || 0) > 0);
    setText('rail-pending-sites', summary.pending);
    setText('rail-ignored-sites', summary.ignored);
    setText('rail-registry-status', sites.length ? 'OK' : 'Review', sites.length ? 'ok' : 'review');
    const users = userCount(root);
    setText('rail-users-count', users === null ? 'Unavailable' : users);
    setText('rail-alert-count', summary.review);
  }

  
// JOM_ESTATE_CONDITIONAL_LIFECYCLE_QUEUES_V1_JS START
function lifecycleQueueState(site) {
  const state = normaliseState(site);
  const label = lifecycleLabel(site);
  if (isIgnored(site)) return 'ignored';
  if (state.includes('delete') || state.includes('deletion')) return 'deletion';
  if (!isMonitored(site) && label === 'Approval Pending') return 'approval';
  return '';
}

function setLifecyclePanel(panelId, countId, listId, sites, emptyText) {
  const panel = document.getElementById(panelId);
  const list = document.getElementById(listId);
  setText(countId, sites.length);
  if (!panel) return;
  panel.hidden = sites.length === 0;
  panel.setAttribute('aria-hidden', sites.length === 0 ? 'true' : 'false');
  if (!list) return;
  if (!sites.length) {
    list.innerHTML = '<p class="estate-empty">' + escapeHtml(emptyText) + '</p>';
    return;
  }
  list.innerHTML = 'SiteLifecycleMonitoringHealthActions' +
    sites.map(site => {
      const lifecycle = lifecycleLabel(site);
      const monitoring = lifecycle === 'Approval Pending' ? 'Pending' : isIgnored(site) ? 'Ignored' : 'Stopped';
      const health = isIgnored(site) ? 'Ignored' : lifecycle === 'Approval Pending' ? 'Review' : 'Removal';
      return '' + siteCell(site) + statusCell(lifecycle) + statusCell(monitoring) + statusCell(health) + '' + reviewLink(site, isIgnored(site) ? 'Restore / Review' : 'Review Site') + atlassianLink(site) + '' + '';
    }).join('') + '';
}

function setLifecycleRailVisibility(kind, count) {
  const row = document.querySelector('[data-lifecycle-rail="' + kind + '"]');
  if (!row) return;
  row.hidden = count === 0;
  row.setAttribute('aria-hidden', count === 0 ? 'true' : 'false');
}

function renderConditionalLifecycleQueues(sites) {
  const deletion = sites.filter(site => lifecycleQueueState(site) === 'deletion');
  const ignored = sites.filter(site => lifecycleQueueState(site) === 'ignored');
  setLifecyclePanel('deletion-sites', 'estate-deletion-count', 'estate-deletion-list', deletion, 'No deletion queue items are currently recorded.');
  setLifecyclePanel('ignored-sites', 'estate-ignored-count', 'estate-ignored-list', ignored, 'No ignored sites are currently recorded.');
  setText('rail-ignored-sites', ignored.length);
  setText('rail-deletion-sites', deletion.length);
  setLifecycleRailVisibility('ignored', ignored.length);
  setLifecycleRailVisibility('deletion', deletion.length);
}
// JOM_ESTATE_CONDITIONAL_LIFECYCLE_QUEUES_V1_JS END
function render(payload) {
    const root = unwrap(payload);
    const sites = sitesFromPayload(root);
    const summary = summaryFromSites(sites);
    renderReviewQueue(sites);
    renderRegistry(sites);
    updateRail(root, sites, summary);
renderConditionalLifecycleQueues(sites);
  }

  function renderError(error) {
    const review = document.getElementById('estate-review-list');
    const body = document.getElementById('estate-registry-body');
    if (review) review.innerHTML = '<p class="estate-empty">Estate workspace contract could not be loaded.</p>';
    if (body) body.innerHTML = '<tr><td colspan="5">Estate workspace contract could not be loaded: ' + escapeHtml(error && error.message ? error.message : error) + '</td></tr>';
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


// JOM_ESTATE_REMOVE_APPROVAL_PENDING_QUEUE_V1 START
// Standalone Approval Pending queue removed; approval pending remains inside Discovery Review Queue.
// JOM_ESTATE_REMOVE_APPROVAL_PENDING_QUEUE_V1 END


// JOM_ESTATE_STOP_MONITORING_REVIEW_QUEUE_V1
// Stopped monitoring returns to Discovery Review Queue, not Deletion Queue.



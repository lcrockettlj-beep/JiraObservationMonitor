// JOM Estate Operational Truth Alignment v1
// Single-owner Estate page renderer. Aligns Estate rail, discovery queue, users and alerts to active workspace truth.
(function(){
  'use strict';
  let inventory = {};
  let workspace = {};
  let sites = [];

  const byId = id => document.getElementById(id);
  const set = (id, value) => { const el = byId(id); if (el) el.textContent = value === null || value === undefined || value === '' ? 'n/a' : String(value); };
  const arr = value => Array.isArray(value) ? value : [];
  const num = (value, fallback) => { const n = Number(value); return Number.isFinite(n) ? n : fallback; };
  const esc = value => String(value ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#039;');
  const unwrap = payload => payload && typeof payload === 'object' && payload.data && typeof payload.data === 'object' ? payload.data : (payload && typeof payload === 'object' ? payload : {});

  async function fetchJson(url){
    const response = await fetch(url, {cache:'no-store'});
    if(!response.ok) throw new Error(url + ' returned ' + response.status);
    return await response.json();
  }

  function siteKey(site){ return site.site_key || site.key || site.name || site.site_name || 'site'; }
  function siteName(site){ return site.name || site.site_name || site.site_key || site.key || 'Unknown site'; }
  function siteUrl(site){ return site.url || site.site_url || ''; }
  function lifecycle(site){ return String(site.lifecycle || site.classification || site.collector_onboarding_status || site.status || 'discovery_gap').toLowerCase(); }
  function isMonitored(site){ return lifecycle(site) === 'monitored' || site.approved_monitored === true || site.is_monitored === true || site.monitored === true; }
  function isReview(site){ return ['pending_review','registered_review','approval_pending','pending'].includes(lifecycle(site)); }
  function isApprovalPending(site){ return ['registered_review','approval_pending'].includes(lifecycle(site)); }
  function isDiscoveryGap(site){ return lifecycle(site) === 'discovery_gap'; }
  function isIgnored(site){ return lifecycle(site) === 'ignored'; }

  function summary(){
    const invSummary = inventory.summary || {};
    const total = num(invSummary.total_inventory_rows ?? invSummary.total_sites, sites.length);
    const monitored = num(invSummary.monitored_count, sites.filter(isMonitored).length);
    const pendingReview = num(invSummary.pending_review_count, sites.filter(s => lifecycle(s) === 'pending_review').length);
    const approvalPending = num(invSummary.registered_review_count ?? invSummary.approval_pending_count, sites.filter(isApprovalPending).length);
    const discoveryGap = num(invSummary.discovery_gap_count, sites.filter(isDiscoveryGap).length);
    const ignored = num(invSummary.ignored_count, sites.filter(isIgnored).length);
    const discovered = total;
    return {total, monitored, discovered, pendingReview, approvalPending, discoveryGap, ignored, reviewQueue: pendingReview};
  }

  function setRailLabel(id, value){
    const dd = byId(id);
    if(!dd) return;
    const row = dd.closest('div');
    const dt = row ? row.querySelector('dt') : null;
    if(dt) dt.textContent = value;
  }

  function usersMetric(){
    const root = unwrap(workspace);
    const candidates = [
      root.users && root.users.metric,
      root.users_metric && root.users_metric.metric,
      root.users_metric,
      root.estate_product_access && root.estate_product_access.summary && root.estate_product_access.summary.total_jira_product_user_count,
      root.estate_access_truth && root.estate_access_truth.product_summary && root.estate_access_truth.product_summary.total_jira_product_user_count,
      root.estate_access_truth && root.estate_access_truth.summary && root.estate_access_truth.summary.api_product_user_count
    ];
    for(const candidate of candidates){ const n = num(candidate, null); if(n !== null) return n; }
    return null;
  }

  function alertCount(){
    const root = unwrap(workspace);
    if(root.operator_alerts && Array.isArray(root.operator_alerts.alerts)) return root.operator_alerts.alerts.length;
    if(root.operator_alerts && root.operator_alerts.count !== undefined) return num(root.operator_alerts.count, 0);
    return 0;
  }

  function renderRail(){
    const s = summary();
    setRailLabel('rail-discovered-sites', 'Discovered');
    setRailLabel('rail-review-queue', 'Requires Review');
    setRailLabel('rail-pending-sites', 'Approval Pending');
    setTextPurpose();
    set('rail-total-sites', s.total);
    set('rail-monitored-sites', s.monitored);
    set('rail-discovered-sites', s.discovered);
    set('rail-review-queue', s.reviewQueue);
    set('rail-pending-sites', s.approvalPending);
    set('rail-ignored-sites', s.ignored);
    set('rail-registry-status', inventory.ok === false ? 'Review' : 'OK');
    const users = usersMetric();
    set('rail-users-count', users === null ? '--' : users);
    set('rail-alert-count', alertCount());
  }

  function setTextPurpose(){
    const heading = document.querySelector('#discovered-sites h2');
    if(heading) heading.textContent = 'Estate Discovery Queue';
    const count = byId('estate-review-count');
    if(count) count.setAttribute('title', 'All sites currently known to Estate discovery inventory.');
    const section = document.querySelector('#discovered-sites .estate-muted');
    if(section) section.textContent = 'All sites found by live discovery, OAuth/resource evidence, admin event references, or known discovery-gap targets. Review actions appear where a lifecycle decision is still needed.';
  }

  function renderDiscoveryQueue(){
    const list = byId('estate-review-list');
    const count = byId('estate-review-count');
    if(count) count.textContent = String(sites.length);
    if(!list) return;
    if(!sites.length){ list.innerHTML = '<p class="estate-empty">No estate sites have been discovered.</p>'; return; }
    list.innerHTML = sites.map(site => {
      const key = encodeURIComponent(siteKey(site));
      const life = lifecycle(site);
      const action = isMonitored(site) ? 'Monitored' : (isReview(site) ? 'Review' : (isDiscoveryGap(site) ? 'Discovery Gap' : 'Review'));
      return '<div class="estate-review-item">'
        + '<strong>' + esc(siteName(site)) + '</strong>'
        + '<span class="estate-muted">' + esc(life.replace(/_/g, ' ')) + '</span>'
        + '<a class="estate-site-link estate-site-link--button" href="/estate/review/' + key + '">' + esc(action) + '</a>'
        + '</div>';
    }).join('');
  }

  function registryVisibleSites(){ return sites.filter(isMonitored); }
  function searchMatch(site, query){
    const q = String(query || '').trim().toLowerCase();
    if(!q) return true;
    return [siteName(site), siteUrl(site), siteKey(site), lifecycle(site), arr(site.sources).join(' ')].join(' ').toLowerCase().includes(q);
  }
  function filteredRegistrySites(){
    const q = byId('estate-search') ? byId('estate-search').value : '';
    return registryVisibleSites().filter(site => searchMatch(site, q));
  }
  function renderRegistryRows(rows){
    const body = byId('estate-registry-body');
    if(!body) return;
    if(!rows.length){ body.innerHTML = '<tr><td colspan="6">No monitored sites match the current search.</td></tr>'; return; }
    body.innerHTML = rows.map(site => {
      const key = encodeURIComponent(siteKey(site));
      const url = siteUrl(site);
      const label = esc(siteName(site));
      const siteCell = url ? '<a class="estate-site-link" href="' + esc(url) + '" target="_blank" rel="noopener noreferrer">' + label + '</a>' : label;
      const last = inventory.generated_utc || inventory.generated_at_utc || site.generated_at_utc || 'Source timestamp unavailable';
      return '<tr>'
        + '<td>' + siteCell + '</td>'
        + '<td>' + esc(lifecycle(site)) + '</td>'
        + '<td>' + (isMonitored(site) ? 'Monitored' : 'Not monitored') + '</td>'
        + '<td>' + (isMonitored(site) ? 'OK' : 'Review') + '</td>'
        + '<td>' + esc(last) + '</td>'
        + '<td><a class="estate-site-link estate-site-link--button" href="/estate/review/' + key + '">Manage</a></td>'
        + '</tr>';
    }).join('');
  }

  function renderError(error){
    const message = error && error.message ? error.message : String(error || 'Unknown error');
    const list = byId('estate-review-list');
    const body = byId('estate-registry-body');
    if(list) list.innerHTML = '<p class="estate-empty">Estate render error: ' + esc(message) + '</p>';
    if(body) body.innerHTML = '<tr><td colspan="6">Estate render error: ' + esc(message) + '</td></tr>';
    set('rail-registry-status', 'Review');
  }

  async function load(){
    try{
      const results = await Promise.allSettled([
        fetchJson('/api/estate/admin-site-inventory'),
        fetchJson('/api/workspace/command-centre')
      ]);
      if(results[0].status !== 'fulfilled') throw results[0].reason;
      inventory = results[0].value || {};
      workspace = results[1].status === 'fulfilled' ? results[1].value : {};
      sites = arr(inventory.sites);
      renderRail();
      renderDiscoveryQueue();
      renderRegistryRows(filteredRegistrySites());
    }catch(error){
      console.warn('Estate operational truth render failed', error);
      renderError(error);
    }
  }

  function init(){
    const search = byId('estate-search');
    const filter = byId('estate-filter');
    if(search) search.addEventListener('input', () => renderRegistryRows(filteredRegistrySites()));
    if(filter) filter.addEventListener('change', () => renderRegistryRows(filteredRegistrySites()));
    load();
  }

  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();

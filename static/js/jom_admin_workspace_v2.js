
// JOM Admin Workspace Expansion v2
(function(){
  const $ = (id) => document.getElementById(id);
  const text = (id, value) => { const el = $(id); if(el) el.textContent = value == null ? 'Unavailable' : String(value); };
  const json = (id, value) => { const el = $(id); if(el) el.textContent = JSON.stringify(value || {}, null, 2); };
  async function fetchJson(path){
    const res = await fetch(path, {cache:'no-store'});
    if(!res.ok) throw new Error(path + ' returned ' + res.status);
    return await res.json();
  }
  function num(v, fallback=0){ const n = Number(v); return Number.isFinite(n) ? n : fallback; }
  function arr(v){ return Array.isArray(v) ? v : []; }
  function setPill(id, value, mode){
    const el = $(id); if(!el) return;
    el.textContent = value;
    el.className = 'admin-v2-pill admin-v2-pill--' + (mode || 'info');
  }
  function registrySummary(registry){
    const s = registry && registry.summary ? registry.summary : {};
    const sites = arr(registry && registry.sites);
    return {
      total: num(s.total_sites, sites.length),
      monitored: num(s.monitored_count, sites.filter(x => x.monitored === true || x.monitoring_state === 'monitored').length),
      discovered: num(s.discovered_count, sites.filter(x => x.monitored === false || x.monitoring_state === 'discovered').length),
      pending: num(s.pending_onboarding_count, 0),
      sites
    };
  }
  function userSummary(footprint){ return footprint && footprint.summary ? footprint.summary : {}; }
  function renderDiscoveryTable(registry){
    const table = $('admin-v2-discovery-table-body'); if(!table) return;
    const reg = registrySummary(registry);
    const rows = reg.sites.filter(site => !(site.monitored === true || site.monitoring_state === 'monitored')).slice(0, 20);
    if(!rows.length){
      table.innerHTML = '<tr><td colspan="4">No unmonitored discovery items currently require review.</td></tr>';
      return;
    }
    table.innerHTML = rows.map(site => {
      const key = site.key || site.site_key || site.name || site.url || 'unknown';
      const name = site.name || site.display_name || key;
      const state = site.monitoring_state || (site.monitored ? 'monitored' : 'discovered');
      const url = site.url || site.base_url || '';
      return `<tr><td><strong>${name}</strong><br><span class="admin-v2-sub">${key}</span></td><td>${state}</td><td>${url || 'No URL listed'}</td><td><span class="admin-v2-pill admin-v2-pill--review">Review</span></td></tr>`;
    }).join('');
  }
  function renderNamedAccess(users){
    const list = $('admin-v2-named-access-list'); if(!list) return;
    const safe = users && users.safe_to_show_named_access_ui;
    const summary = userSummary(users);
    const rows = [
      ['Named access UI', safe ? 'Safe to show' : 'Review required', safe ? 'ok' : 'review'],
      ['Users analysed', summary.users_analyzed || summary.named_unique_users || '0', 'info'],
      ['High duplication users', summary.high_duplication_users || '0', num(summary.high_duplication_users,0) ? 'review' : 'ok'],
      ['Medium duplication users', summary.medium_duplication_users || '0', num(summary.medium_duplication_users,0) ? 'review' : 'ok'],
      ['Product assignments', summary.total_product_access_assignments || summary.reconciled_api_product_users || '0', 'info']
    ];
    list.innerHTML = rows.map(([label,value,mode]) => `<li><span>${label}</span><span class="admin-v2-pill admin-v2-pill--${mode}">${value}</span></li>`).join('');
  }
  function renderRuntime(summary, observability, sourceState){
    const list = $('admin-v2-runtime-list'); if(!list) return;
    const runtime = summary && summary.runtime ? summary.runtime : {};
    const obs = observability && observability.runtime_status ? observability.runtime_status : {};
    const sourceSchema = sourceState && sourceState.schema;
    const rows = [
      ['Runtime state', runtime.last_result_status || runtime.state || 'unknown', (runtime.last_result_status === 'ok' || runtime.state === 'idle') ? 'ok' : 'review'],
      ['Running', runtime.running ? 'Running' : 'Idle', runtime.running ? 'review' : 'ok'],
      ['Last refresh', runtime.last_finished_at_utc || runtime.last_started_at_utc || 'Unavailable', 'info'],
      ['Observability', obs.state || 'available', 'info'],
      ['Source state', sourceSchema ? 'Available' : 'Review', sourceSchema ? 'ok' : 'review']
    ];
    list.innerHTML = rows.map(([label,value,mode]) => `<li><span>${label}</span><span class="admin-v2-pill admin-v2-pill--${mode}">${value}</span></li>`).join('');
  }
  function renderApiConnections(adminTruth, users, registry, sourceState){
    const list = $('admin-v2-api-list'); if(!list) return;
    const rows = [
      ['Admin truth', adminTruth && adminTruth.schema ? 'Connected' : 'Loaded', 'ok'],
      ['User footprint', users && users.schema ? 'Connected' : 'Loaded', 'ok'],
      ['Registry', registry && registry.schema ? 'Connected' : 'Loaded', 'ok'],
      ['Source state', sourceState && sourceState.schema ? 'Connected' : 'Loaded', 'ok']
    ];
    list.innerHTML = rows.map(([label,value,mode]) => `<li><span>${label}</span><span class="admin-v2-pill admin-v2-pill--${mode}">${value}</span></li>`).join('');
  }
  async function init(){
    const root = document.querySelector('[data-admin-workspace-v2="true"]');
    if(!root) return;
    try{
      const [adminTruth, users, registry, summary, observability, sourceState] = await Promise.all([
        fetchJson('/admin/truth'),
        fetchJson('/users/footprint'),
        fetchJson('/registry/sites'),
        fetchJson('/operator/summary'),
        fetchJson('/operator/observability'),
        fetchJson('/api/source-state')
      ]);
      const reg = registrySummary(registry);
      const us = userSummary(users);
      text('admin-v2-total-sites', reg.total);
      text('admin-v2-monitored-sites', reg.monitored);
      text('admin-v2-discovered-sites', reg.discovered);
      text('admin-v2-users', us.users_analyzed || us.named_unique_users || arr(users.users).length || '0');
      text('admin-v2-assignments', us.total_product_access_assignments || us.reconciled_api_product_users || '0');
      setPill('admin-v2-named-access-status', users.safe_to_show_named_access_ui ? 'Safe to show' : 'Review required', users.safe_to_show_named_access_ui ? 'ok' : 'review');
      setPill('admin-v2-source-health', sourceState && sourceState.schema ? 'Source state available' : 'Review source state', sourceState && sourceState.schema ? 'ok' : 'review');
      setPill('admin-v2-runtime-health', summary.runtime && (summary.runtime.last_result_status === 'ok' || summary.runtime.state === 'idle') ? 'Runtime healthy' : 'Review runtime', summary.runtime && (summary.runtime.last_result_status === 'ok' || summary.runtime.state === 'idle') ? 'ok' : 'review');
      renderDiscoveryTable(registry);
      renderNamedAccess(users);
      renderRuntime(summary, observability, sourceState);
      renderApiConnections(adminTruth, users, registry, sourceState);
      json('admin-v2-admin-truth-json', adminTruth);
      json('admin-v2-users-json', users);
      json('admin-v2-source-json', sourceState);
    }catch(error){
      console.warn('Admin Workspace Expansion v2 failed', error);
      setPill('admin-v2-source-health', 'Load failed', 'review');
    }
  }
  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();

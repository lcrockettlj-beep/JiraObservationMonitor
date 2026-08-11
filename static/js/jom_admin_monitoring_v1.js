(function(){
  'use strict';
  const ENDPOINT = '/api/admin/monitoring';
  const REFRESH_ENDPOINT = '/api/admin/monitoring/refresh';
  let refreshPolls = 0;
  const text = (id, value) => { const el = document.getElementById(id); if (el) el.textContent = value === null || value === undefined || value === '' ? 'Unavailable' : String(value); };
  const html = (id, value) => { const el = document.getElementById(id); if (el) el.innerHTML = value; };
  const esc = value => String(value ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
  const fmt = value => value === null || value === undefined || value === '' ? 'Unavailable' : (Number.isFinite(Number(value)) ? Number(value).toLocaleString() : String(value));
  const pct = value => value === null || value === undefined || value === '' ? 'Unavailable' : fmt(value) + '%';
  const status = value => {
    const raw = String(value ?? '').trim().toLowerCase();
    if (['ok','healthy','available','enabled','current','generated','aligned','live'].includes(raw)) return {label:'Healthy', tone:'ok'};
    if (['attention','review','warning','aging','partial','stale'].includes(raw)) return {label:'Attention', tone:'attention'};
    if (['failed','failure','error','critical','unavailable','missing','blocked'].includes(raw)) return {label:'Unavailable', tone:'unavailable'};
    return {label: raw ? raw.replace(/[_-]+/g,' ').replace(/\b\w/g, c => c.toUpperCase()) : 'Unavailable', tone:'unavailable'};
  };
  const badge = value => { const item = status(value); return '<span class="site-badge site-badge--' + item.tone + '">' + esc(item.label) + '</span>'; };
  const sourceDescription = label => ({
    'Product access refresh':'Confirms that OAuth-backed Jira product and assignment data was refreshed successfully.',
    'Runtime execution':'Confirms that the Monitoring preflight completed and recorded a current execution result.',
    'Source freshness':'Checks whether required monitoring sources are current enough to use.',
    'Source reliability':'Checks for failed, missing, stale, or guarded monitoring sources.'
  }[label] || 'Checks whether this monitoring source is available and safe to use.');
  const formatTime = value => {
    if (!value) return 'Validation time unavailable';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString([], {dateStyle:'medium', timeStyle:'short'});
  };
  function renderActions(actions){
    const required = (Array.isArray(actions) ? actions : []).filter(item => String(item.level || '').toLowerCase() !== 'ok');
    if (!required.length) {
      html('mon-action-list', '<article class="admin-mon-action-card admin-mon-action-card--ok"><span>Healthy</span><strong>No action required</strong><p>Monitoring coverage and source health are operating normally.</p><p><b>Next:</b> No operator action is required. Continue routine review.</p></article>');
      return 0;
    }
    html('mon-action-list', required.map(item => '<article class="admin-mon-action-card"><span>' + esc(status(item.level).label) + '</span><strong>' + esc(item.title || 'Action required') + '</strong><p>' + esc(item.reason || '') + '</p><p><b>Next:</b> ' + esc(item.action || 'Review the affected monitoring source.') + '</p></article>').join(''));
    return required.length;
  }
  function renderSites(rows){
    if (!Array.isArray(rows) || !rows.length) { html('mon-sites-body', '<tr><td colspan="4">No monitored site rows are available.</td></tr>'); return; }
    html('mon-sites-body', rows.map(row => '<tr><td><strong>' + esc(row.site_name || row.site_key) + '</strong><br><small>' + esc(row.site_key || '') + '</small></td><td>' + badge(row.monitoring) + '</td><td>' + badge(row.product_access_status) + '</td><td>' + esc(fmt(row.product_users)) + '</td></tr>').join(''));
  }
  function renderSources(sourceHealth){
    const items = sourceHealth && typeof sourceHealth === 'object' ? Object.values(sourceHealth) : [];
    if (!items.length) { html('mon-source-health', '<article class="admin-mon-source-card"><strong>Unavailable</strong><p>No monitoring health information was returned.</p></article>'); return; }
    html('mon-source-health', items.map(item => { const shown = status(item.status); return '<article class="admin-mon-source-card admin-mon-source-card--' + shown.tone + '"><span>' + esc(item.label || 'Monitoring source') + '</span><strong>' + esc(shown.label) + '</strong><p>' + esc(sourceDescription(item.label)) + '</p><small>Last checked: ' + esc(formatTime(item.generated_at_utc)) + '</small></article>'; }).join(''));
  }
  function render(data){
    const summary = data.summary || {}, actions = Array.isArray(data.actions) ? data.actions : [];
    const overall = status(data.status);
    text('mon-authority-status', overall.label);
    text('mon-authority-note', overall.tone === 'ok' ? 'All monitored sites are covered and no monitoring sources require attention.' : 'One or more monitoring checks require review. See Operational decisions for the next action.');
    text('mon-total-sites', fmt(summary.total_sites));
    text('mon-monitored-sites', fmt(summary.monitored_sites));
    text('mon-coverage', pct(summary.monitoring_coverage_percent));
    text('mon-product-sites', fmt(summary.product_access_sites));
    text('mon-product-users', fmt(summary.product_users));
    text('mon-failed-sources', fmt(summary.failed_sources));
    text('mon-rail-coverage', pct(summary.monitoring_coverage_percent));
    text('mon-rail-sites', fmt(summary.monitored_sites));
    text('mon-rail-failed', fmt(summary.failed_sources));
    text('mon-rail-actions', fmt(renderActions(actions)));
    text('mon-last-validation', formatTime(data.generated_at_utc));
    renderSites(data.sites);
    renderSources(data.source_health);
  }
  function fail(error){ text('mon-authority-status', 'Unavailable'); text('mon-authority-note', error && error.message ? error.message : 'Monitoring contract unavailable.'); html('mon-action-list', '<article class="admin-mon-action-card"><strong>Monitoring unavailable</strong><p>The Monitoring contract could not be loaded.</p></article>'); }
  function loadCurrent(){ return fetch(ENDPOINT,{cache:'no-store',headers:{'Accept':'application/json'}}).then(r=>{if(!r.ok)throw new Error(ENDPOINT+' returned HTTP '+r.status);return r.json();}).then(data=>{render(data);return data;}); }
  function pollRefresh(){ window.setTimeout(()=>{loadCurrent().then(data=>{const refresh=data.authority&&data.authority.refresh?data.authority.refresh:{};if(refresh.running&&refreshPolls<30){refreshPolls+=1;pollRefresh();}}).catch(()=>{});},2000); }
  function startBackgroundRefresh(){ fetch(REFRESH_ENDPOINT,{method:'POST',cache:'no-store',headers:{'Accept':'application/json'}}).then(r=>r.json()).then(()=>{refreshPolls=0;pollRefresh();}).catch(()=>{}); }
  function boot(){ loadCurrent().then(startBackgroundRefresh).catch(fail); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
}());

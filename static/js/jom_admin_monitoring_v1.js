(function(){
  'use strict';
  const ENDPOINT = '/api/admin/monitoring';
  const text = (id, value) => { const el = document.getElementById(id); if (el) el.textContent = value === null || value === undefined || value === '' ? 'Unavailable' : String(value); };
  const html = (id, value) => { const el = document.getElementById(id); if (el) el.innerHTML = value; };
  const esc = value => String(value ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
  const fmt = value => value === null || value === undefined || value === '' ? 'Unavailable' : (Number.isFinite(Number(value)) ? Number(value).toLocaleString() : String(value));
  const pct = value => value === null || value === undefined || value === '' ? 'Unavailable' : fmt(value) + '%';
  const badge = value => '<span class="site-badge site-badge--' + (String(value).toLowerCase().includes('ok') || String(value).toLowerCase().includes('enabled') || String(value).toLowerCase().includes('live') || String(value).toLowerCase().includes('available') ? 'ok' : 'review') + '">' + esc(value || 'review') + '</span>';
  function renderActions(actions){
    if (!Array.isArray(actions) || !actions.length) { html('mon-action-list', '<article class="admin-mon-action-card"><strong>No immediate monitoring actions</strong><p>Current monitoring authority did not return priority action items.</p></article>'); return; }
    html('mon-action-list', actions.map(item => '<article class="admin-mon-action-card"><span>' + esc(item.level || 'review') + '</span><strong>' + esc(item.title || 'Action required') + '</strong><p>' + esc(item.reason || '') + '</p><p><strong>Next:</strong> ' + esc(item.action || 'Review authority source.') + '</p></article>').join(''));
  }
  function renderSites(rows){
    if (!Array.isArray(rows) || !rows.length) { html('mon-sites-body', '<tr><td colspan="5">No monitored site rows are available from authority.</td></tr>'); return; }
    html('mon-sites-body', rows.map(row => '<tr><td><strong>' + esc(row.site_name || row.site_key) + '</strong><br><small>' + esc(row.site_key || '') + '</small></td><td>' + badge(row.monitoring) + '</td><td>' + badge(row.product_access_status) + '</td><td>' + esc(fmt(row.product_users)) + '</td><td>' + esc(fmt(row.role_count)) + '</td></tr>').join(''));
  }
  function renderSources(sourceHealth){
    const items = sourceHealth && typeof sourceHealth === 'object' ? Object.values(sourceHealth) : [];
    if (!items.length) { html('mon-source-health', '<article class="admin-mon-source-card"><strong>Unavailable</strong><p>No source health authority was available.</p></article>'); return; }
    html('mon-source-health', items.map(item => '<article class="admin-mon-source-card"><span>' + esc(item.label || 'Source') + '</span><strong>' + esc(item.status || 'unavailable') + '</strong><p>' + esc(item.generated_at_utc || 'Timestamp unavailable') + '</p></article>').join(''));
  }
  function render(data){
    const summary = data.summary || {}, authority = data.authority || {}, actions = Array.isArray(data.actions) ? data.actions : [];
    text('mon-authority-status', data.status === 'ok' ? 'OK' : 'REVIEW');
    text('mon-authority-note', authority.truth_policy || 'Runtime/OAuth authority only.');
    text('mon-total-sites', fmt(summary.total_sites));
    text('mon-monitored-sites', fmt(summary.monitored_sites));
    text('mon-coverage', pct(summary.monitoring_coverage_percent));
    text('mon-product-sites', fmt(summary.product_access_sites));
    text('mon-product-users', fmt(summary.product_users));
    text('mon-failed-sources', fmt(summary.failed_sources));
    text('mon-rail-coverage', pct(summary.monitoring_coverage_percent));
    text('mon-rail-sites', fmt(summary.monitored_sites));
    text('mon-rail-failed', fmt(summary.failed_sources));
    text('mon-rail-actions', fmt(actions.length));
    renderActions(actions);
    renderSites(data.sites);
    renderSources(data.source_health);
  }
  function fail(error){
    text('mon-authority-status', 'Unavailable');
    text('mon-authority-note', error && error.message ? error.message : 'Contract unavailable');
    html('mon-action-list', '<article class="admin-mon-action-card"><strong>Contract unavailable</strong><p>Monitoring authority contract could not be loaded.</p></article>');
  }
  function boot(){ fetch(ENDPOINT, {cache:'no-store', headers:{'Accept':'application/json'}}).then(r => { if(!r.ok) throw new Error(ENDPOINT + ' returned HTTP ' + r.status); return r.json(); }).then(render).catch(fail); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
}());

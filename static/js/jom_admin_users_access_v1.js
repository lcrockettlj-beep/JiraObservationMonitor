(function(){
  'use strict';
  const ENDPOINT = '/api/admin/users-access';
  const text = (id, value) => { const el = document.getElementById(id); if (el) el.textContent = value === null || value === undefined || value === '' ? 'Unavailable' : String(value); };
  const html = (id, value) => { const el = document.getElementById(id); if (el) el.innerHTML = value; };
  const esc = value => String(value ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
  const fmt = value => value === null || value === undefined || value === '' ? 'Unavailable' : (Number.isFinite(Number(value)) ? Number(value).toLocaleString() : String(value));
  const badge = value => '<span class="site-badge site-badge--' + (String(value).toLowerCase().includes('ok') || String(value).toLowerCase().includes('live') ? 'ok' : 'review') + '">' + esc(value || 'review') + '</span>';

  function renderActions(actions){
    if (!Array.isArray(actions) || !actions.length) {
      html('ua-action-list', '<article class="admin-users-action-card"><strong>No immediate user-access actions</strong><p>Current authority-backed user/access checks did not return priority action items.</p></article>');
      return;
    }
    html('ua-action-list', actions.map(item => '<article class="admin-users-action-card"><span>' + esc(item.level || 'review') + '</span><strong>' + esc(item.title || 'Action required') + '</strong><p>' + esc(item.reason || '') + '</p><p><strong>Next:</strong> ' + esc(item.action || 'Review authority source.') + '</p></article>').join(''));
  }
  function renderSites(rows){
    if (!Array.isArray(rows) || !rows.length) { html('ua-sites-body', '<tr><td colspan="4">No monitored site access rows are available from authority.</td></tr>'); return; }
    html('ua-sites-body', rows.map(row => '<tr><td><strong>' + esc(row.site_name || row.site_key) + '</strong><br><small>' + esc(row.site_key || '') + '</small></td><td>' + esc(fmt(row.product_users)) + '</td><td>' + esc(fmt(row.role_count)) + '</td><td>' + badge(row.status || 'review') + '</td></tr>').join(''));
  }
  function render(data){
    const authority = data.authority || {}, summary = data.summary || {}, actions = Array.isArray(data.actions) ? data.actions : [];
    text('ua-authority-status', data.status === 'ok' ? 'LIVE' : 'REVIEW');
    text('ua-authority-note', authority.truth_policy || 'Product-access assignments are not active-user truth.');
    text('ua-active-users', summary.active_users_display || 'Unavailable');
    text('ua-product-access', fmt(summary.product_access_assignments));
    text('ua-monitored-sites', fmt(summary.monitored_sites));
    text('ua-role-rows', fmt(summary.role_rows));
    text('ua-footprint-records', fmt(summary.footprint_records));
    text('ua-issue-count', fmt(summary.issue_count));
    text('ua-critical-count', fmt(summary.critical_count));
    text('ua-risk-count', fmt(summary.risk_count));
    text('ua-waste-count', fmt(summary.waste_count));
    text('ua-drift-count', fmt(summary.drift_count));
    text('ua-rail-active-users', summary.active_users_display || 'Unavailable');
    text('ua-rail-product-access', fmt(summary.product_access_assignments));
    text('ua-rail-sites', fmt(summary.monitored_sites));
    text('ua-rail-role-rows', fmt(summary.role_rows));
    text('ua-rail-issues', fmt(summary.issue_count));
    text('ua-rail-actions', fmt(actions.length));
    renderActions(actions);
    renderSites(data.site_access);
  }
  function fail(error){
    text('ua-authority-status', 'Unavailable');
    text('ua-authority-note', error && error.message ? error.message : 'Contract unavailable');
    html('ua-action-list', '<article class="admin-users-action-card"><strong>Contract unavailable</strong><p>Users & Access authority contract could not be loaded.</p></article>');
  }
  function boot(){ fetch(ENDPOINT, {cache:'no-store', headers:{'Accept':'application/json'}}).then(r => { if(!r.ok) throw new Error(ENDPOINT + ' returned HTTP ' + r.status); return r.json(); }).then(render).catch(fail); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
}());

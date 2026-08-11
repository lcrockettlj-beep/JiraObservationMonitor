(function(){
  'use strict';
  const ENDPOINT = '/api/admin/users-access';
  const text = (id, value) => { const el = document.getElementById(id); if (el) el.textContent = value === null || value === undefined || value === '' ? 'Unavailable' : String(value); };
  const html = (id, value) => { const el = document.getElementById(id); if (el) el.innerHTML = value; };
  const esc = value => String(value ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
  const fmt = value => value === null || value === undefined || value === '' ? 'Unavailable' : (Number.isFinite(Number(value)) ? Number(value).toLocaleString() : String(value));
  const status = value => {
    const raw = String(value ?? '').trim().toLowerCase();
    if (['ok','healthy','available','enabled','current','generated','aligned','live'].includes(raw)) return {label:'Healthy', tone:'ok'};
    if (['attention','review','warning','aging','partial','stale'].includes(raw)) return {label:'Attention', tone:'attention'};
    if (['failed','failure','error','critical','unavailable','missing','blocked'].includes(raw)) return {label:'Unavailable', tone:'unavailable'};
    return {label: raw ? raw.replace(/[_-]+/g,' ').replace(/\b\w/g, c => c.toUpperCase()) : 'Unavailable', tone:'unavailable'};
  };
  const badge = value => { const item = status(value); return '<span class="site-badge site-badge--' + item.tone + '">' + esc(item.label) + '</span>'; };
  const formatTime = value => {
    if (!value) return 'Validation time unavailable';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString([], {dateStyle:'medium', timeStyle:'short'});
  };
  function renderActions(actions){
    const items = Array.isArray(actions) ? actions : [];
    const required = items.filter(item => String(item.level || '').toLowerCase() !== 'ok');
    if (!required.length) {
      html('ua-action-list', '<article class="admin-users-action-card admin-users-action-card--ok"><span>Healthy</span><strong>No action required</strong><p>Current user and access authority did not return a priority action.</p></article>');
      return 0;
    }
    html('ua-action-list', required.map(item => {
      const shown = status(item.level);
      return '<article class="admin-users-action-card admin-users-action-card--' + shown.tone + '"><span>' + esc(shown.label) + '</span><strong>' + esc(item.title || 'Action required') + '</strong><p>' + esc(item.reason || '') + '</p><p><b>Next:</b> ' + esc(item.action || 'Review the affected authority source.') + '</p></article>';
    }).join(''));
    return required.length;
  }
  function renderSites(rows){
    if (!Array.isArray(rows) || !rows.length) {
      html('ua-sites-body', '<tr><td colspan="3">No monitored site access rows are available.</td></tr>');
      return;
    }
    html('ua-sites-body', rows.map(row => '<tr><td><strong>' + esc(row.site_name || row.site_key) + '</strong><br><small>' + esc(row.site_key || '') + '</small></td><td>' + esc(fmt(row.product_users)) + '</td><td>' + badge(row.status) + '</td></tr>').join(''));
  }
  function render(data){
    const authority = data.authority || {};
    const summary = data.summary || {};
    const overall = status(data.status);
    const actionCount = renderActions(data.actions);
    text('ua-authority-status', overall.label);
    text('ua-authority-note', authority.active_user_authority === 'unavailable' ? 'Jira access assignments are available, but unique active users are not currently proven.' : (authority.truth_policy || 'Current user and access authority is available.'));
    text('ua-active-users', summary.active_users_display || 'Unavailable');
    text('ua-product-access', fmt(summary.product_access_assignments));
    text('ua-monitored-sites', fmt(summary.monitored_sites));
    text('ua-footprint-records', fmt(summary.footprint_records));
    text('ua-critical-count', fmt(summary.critical_count));
    text('ua-risk-count', fmt(summary.risk_count));
    text('ua-waste-count', fmt(summary.waste_count));
    text('ua-drift-count', fmt(summary.drift_count));
    text('ua-rail-active-users', summary.active_users_display || 'Unavailable');
    text('ua-rail-observed-users', fmt(summary.footprint_records));
    text('ua-rail-product-access', fmt(summary.product_access_assignments));
    text('ua-rail-sites', fmt(summary.monitored_sites));
    text('ua-rail-issues', fmt(summary.issue_count));
    text('ua-rail-actions', fmt(actionCount));
    text('ua-last-validation', formatTime(data.generated_at_utc));
    renderSites(data.site_access);
  }
  function fail(error){
    text('ua-authority-status', 'Unavailable');
    text('ua-authority-note', error && error.message ? error.message : 'Users and Access contract unavailable.');
    html('ua-action-list', '<article class="admin-users-action-card admin-users-action-card--unavailable"><strong>Users and Access unavailable</strong><p>The authority contract could not be loaded.</p></article>');
  }
  function boot(){
    fetch(ENDPOINT, {cache:'no-store', headers:{'Accept':'application/json'}})
      .then(response => { if (!response.ok) throw new Error(ENDPOINT + ' returned HTTP ' + response.status); return response.json(); })
      .then(render)
      .catch(fail);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
}());

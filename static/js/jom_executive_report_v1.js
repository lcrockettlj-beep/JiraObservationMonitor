(function(){
  'use strict';
  const ENDPOINT = '/api/reporting/executive-report';
  const text = (id, value) => { const el = document.getElementById(id); if (el) el.textContent = value === null || value === undefined || value === '' ? 'Unavailable' : String(value); };
  const html = (id, value) => { const el = document.getElementById(id); if (el) el.innerHTML = value; };
  const esc = value => String(value ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
  const fmt = value => value === null || value === undefined || value === '' ? 'Unavailable' : (Number.isFinite(Number(value)) ? Number(value).toLocaleString() : String(value));
  const pct = value => value === null || value === undefined || value === '' ? 'Unavailable' : fmt(value) + '%';
  function renderActions(actions){
    if (!Array.isArray(actions) || !actions.length) { html('exec-action-list', '<article class="exec-action-card"><strong>No immediate executive actions</strong><p>Current authority did not return priority executive actions.</p></article>'); return; }
    html('exec-action-list', actions.map(item => '<article class="exec-action-card"><span>' + esc(item.level || 'review') + '</span><strong>' + esc(item.title || 'Action required') + '</strong><p>' + esc(item.reason || '') + '</p><p><strong>Next:</strong> ' + esc(item.action || 'Review authority source.') + '</p></article>').join(''));
  }
  function renderMessages(messages){
    if (!Array.isArray(messages) || !messages.length) { html('exec-board-messages', '<article class="exec-message-card"><strong>No current narrative messages</strong><p>No board messages returned by authority.</p></article>'); return; }
    html('exec-board-messages', messages.map((msg, i) => '<article class="exec-message-card"><span>Message ' + (i + 1) + '</span><strong>' + esc(msg) + '</strong></article>').join(''));
  }
  function renderSources(sourceHealth){
    const items = sourceHealth && typeof sourceHealth === 'object' ? Object.values(sourceHealth) : [];
    if (!items.length) { html('exec-source-health', '<article class="exec-source-card"><strong>Unavailable</strong><p>No source assurance state was available.</p></article>'); return; }
    html('exec-source-health', items.map(item => '<article class="exec-source-card"><span>' + esc(item.label || 'Source') + '</span><strong>' + esc(item.status || 'unavailable') + '</strong><p>' + esc(item.generated_at_utc || 'Timestamp unavailable') + '</p></article>').join(''));
  }
  function render(data){
    const summary = data.summary || {}, authority = data.authority || {}, actions = Array.isArray(data.actions) ? data.actions : [];
    text('exec-status', data.status === 'ok' ? 'OK' : 'REVIEW');
    text('exec-authority-note', authority.truth_policy || 'Runtime/OAuth/Admin authority only.');
    text('exec-total-sites', fmt(summary.total_sites));
    text('exec-monitored-sites', fmt(summary.monitored_sites));
    text('exec-coverage', pct(summary.monitoring_coverage_percent));
    text('exec-product-access', fmt(summary.product_access_assignments));
    text('exec-active-users', summary.active_users_display || 'Unavailable');
    text('exec-billing', summary.commercial_billing_display || 'Unavailable');
    text('exec-rail-coverage', pct(summary.monitoring_coverage_percent));
    text('exec-rail-sites', fmt(summary.monitored_sites));
    text('exec-rail-product-access', fmt(summary.product_access_assignments));
    text('exec-rail-failed', fmt(summary.failed_sources));
    text('exec-rail-actions', fmt(actions.length));
    renderActions(actions);
    renderMessages(data.board_messages);
    renderSources(data.source_health);
  }
  function fail(error){
    text('exec-status', 'Unavailable');
    text('exec-authority-note', error && error.message ? error.message : 'Contract unavailable');
    html('exec-action-list', '<article class="exec-action-card"><strong>Contract unavailable</strong><p>Executive Report authority contract could not be loaded.</p></article>');
  }
  function boot(){ fetch(ENDPOINT, {cache:'no-store', headers:{'Accept':'application/json'}}).then(r => { if(!r.ok) throw new Error(ENDPOINT + ' returned HTTP ' + r.status); return r.json(); }).then(render).catch(fail); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
}());

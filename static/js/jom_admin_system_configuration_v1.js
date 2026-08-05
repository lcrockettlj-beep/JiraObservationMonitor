(function(){
  'use strict';
  const ENDPOINT = '/api/admin/system-configuration';
  const text = (id, value) => { const el = document.getElementById(id); if (el) el.textContent = value === null || value === undefined || value === '' ? 'Unavailable' : String(value); };
  const html = (id, value) => { const el = document.getElementById(id); if (el) el.innerHTML = value; };
  const esc = value => String(value ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
  const fmt = value => value === null || value === undefined || value === '' ? 'Unavailable' : (Number.isFinite(Number(value)) ? Number(value).toLocaleString() : String(value));
  const pct = value => value === null || value === undefined || value === '' ? 'Unavailable' : fmt(value) + '%';
  const titleCase = value => String(value || '').replace(/_/g,' ').replace(/\b\w/g, c => c.toUpperCase());
  function renderActions(actions){
    if (!Array.isArray(actions) || !actions.length) { html('sys-action-list', '<article class="admin-system-action-card"><strong>No immediate configuration actions</strong><p>Current configuration authority did not return priority action items.</p></article>'); return; }
    html('sys-action-list', actions.map(item => '<article class="admin-system-action-card"><span>' + esc(item.level || 'review') + '</span><strong>' + esc(item.title || 'Action required') + '</strong><p>' + esc(item.reason || '') + '</p><p><strong>Next:</strong> ' + esc(item.action || 'Review authority source.') + '</p></article>').join(''));
  }
  function renderSources(sourceHealth){
    const items = sourceHealth && typeof sourceHealth === 'object' ? Object.values(sourceHealth) : [];
    if (!items.length) { html('sys-source-health', '<article class="admin-system-source-card"><strong>Unavailable</strong><p>No source authority was available.</p></article>'); return; }
    html('sys-source-health', items.map(item => '<article class="admin-system-source-card"><span>' + esc(item.label || 'Source') + '</span><strong>' + esc(item.status || 'unavailable') + '</strong><p>' + esc(item.generated_at_utc || 'Timestamp unavailable') + '</p></article>').join(''));
  }
  function renderGuardrails(guardrails){
    const entries = guardrails && typeof guardrails === 'object' ? Object.entries(guardrails) : [];
    if (!entries.length) { html('sys-guardrails', '<article class="admin-system-source-card"><strong>Unavailable</strong><p>No guardrail state was available.</p></article>'); return; }
    html('sys-guardrails', entries.map(([key,value]) => '<article class="admin-system-source-card"><span>' + esc(titleCase(key)) + '</span><strong>' + esc(value === true ? 'Enabled' : 'Review') + '</strong><p>' + esc(value === true ? 'Guardrail is enforced for this page contract.' : 'Guardrail is not proven by this contract.') + '</p></article>').join(''));
  }
  function render(data){
    const summary = data.summary || {}, authority = data.authority || {}, actions = Array.isArray(data.actions) ? data.actions : [];
    text('sys-authority-status', data.status === 'ok' ? 'OK' : 'REVIEW');
    text('sys-authority-note', authority.truth_policy || 'Runtime/OAuth/Admin authority only.');
    text('sys-environment', summary.environment);
    text('sys-runtime-mode', summary.runtime_mode);
    text('sys-monitored-sites', fmt(summary.monitored_sites));
    text('sys-coverage', pct(summary.monitoring_coverage_percent));
    text('sys-configured-sources', fmt(summary.configured_sources));
    text('sys-failed-sources', fmt(summary.failed_sources));
    text('sys-rail-environment', summary.environment);
    text('sys-rail-sources', fmt(summary.configured_sources));
    text('sys-rail-failed', fmt(summary.failed_sources));
    text('sys-rail-guardrails', fmt(summary.guardrails_enabled));
    text('sys-rail-actions', fmt(actions.length));
    renderActions(actions);
    renderSources(data.source_health);
    renderGuardrails(data.guardrails);
  }
  function fail(error){
    text('sys-authority-status', 'Unavailable');
    text('sys-authority-note', error && error.message ? error.message : 'Contract unavailable');
    html('sys-action-list', '<article class="admin-system-action-card"><strong>Contract unavailable</strong><p>System Configuration authority contract could not be loaded.</p></article>');
  }
  function boot(){ fetch(ENDPOINT, {cache:'no-store', headers:{'Accept':'application/json'}}).then(r => { if(!r.ok) throw new Error(ENDPOINT + ' returned HTTP ' + r.status); return r.json(); }).then(render).catch(fail); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
}());

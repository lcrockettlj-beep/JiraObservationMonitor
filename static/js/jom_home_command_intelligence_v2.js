(function(){
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const arr = value => Array.isArray(value) ? value : [];
  const set = (id, value) => { const el = $(id); if(el) el.textContent = value === undefined || value === null || value === '' ? '--' : String(value); };
  async function json(path){ const res = await fetch(path,{cache:'no-store'}); if(!res.ok) throw new Error(path + ' returned ' + res.status); return res.json(); }
  function sites(registry){ return arr(registry.sites); }
  function isMonitored(site){ const value = String(site.classification || site.state || site.status || '').toLowerCase(); return value === 'monitored' || site.monitored === true; }
  function siteKey(site){ return String(site.site_key || site.key || site.name || site.url || 'unknown-site').replace(/^https?:\/\//,'').replace(/\.atlassian\.net.*$/,'').split('/')[0].toLowerCase(); }
  function userCount(footprint){ const s = footprint.summary || {}; return s.users_analyzed ?? arr(footprint.users).length ?? '--'; }
  function assignmentCount(footprint){ const s = footprint.summary || {}; return s.total_product_access_assignments ?? '--'; }
  function alertCount(alerts){ return alerts.count ?? alerts.alert_count ?? 0; }
  function runtimeStatus(summary){ const r = summary.runtime || {}; return r.last_result_status || r.status || r.state || 'unknown'; }
  function healthScore({registry, alerts, summary, sourceState}){ const discovered = sites(registry).filter(s => !isMonitored(s)).length; const ac = Number(alertCount(alerts)) || 0; const rs = runtimeStatus(summary); let score = 100 - Math.min(discovered * 3, 24) - Math.min(ac * 7, 35); if(!/ok|healthy|success|idle/i.test(rs)) score -= 8; if(!sourceState || !Object.keys(sourceState).length) score -= 5; return Math.max(0, Math.min(100, score)); }
  function pill(text,type){ return '<span class="command-v2-pill command-v2-pill--'+type+'">'+esc(text)+'</span>'; }
  function renderRisks(registry, alerts, summary, sourceState){ const target = $('command-v2-risk-list'); if(!target) return; const discovered = sites(registry).filter(s => !isMonitored(s)); const ac = alertCount(alerts); const rs = runtimeStatus(summary); const risks = [];
    if(ac) risks.push(['Active alerts', ac + ' alert(s) require review', 'risk']);
    if(discovered.length) risks.push(['Discovery queue', discovered.length + ' discovered/unmonitored site(s)', 'review']);
    if(!/ok|healthy|success|idle/i.test(rs)) risks.push(['Runtime state', rs, 'review']);
    if(!sourceState || !Object.keys(sourceState).length) risks.push(['Source state', 'Source-state payload unavailable', 'review']);
    if(!risks.length) risks.push(['Current state', 'No critical source-backed issues in current snapshot', 'ok']);
    target.innerHTML = risks.map(([name,detail,type]) => '<li class="command-v2-risk"><span><strong>'+esc(name)+'</strong><br><small>'+esc(detail)+'</small></span>'+pill(type === 'ok' ? 'OK' : 'Review', type)+'</li>').join(''); }
  function renderActions(registry, footprint, alerts, summary){ const target = $('command-v2-action-list'); if(!target) return; const discovered = sites(registry).filter(s => !isMonitored(s)).length; const ac = alertCount(alerts); const users = userCount(footprint); const actions = [];
    if(discovered) actions.push('Review discovered/unmonitored sites in Admin and decide monitor, ignore or investigate.');
    if(ac) actions.push('Open Command Centre alert context and confirm whether active alert needs operational action.');
    actions.push('Use Estate to open a site workspace for any site requiring investigation.');
    actions.push('Use Executive / Estate / Governance reports before stakeholder update.');
    if(users !== '--') actions.push('Use Admin governance depth to validate user footprint and access assignment posture.');
    target.innerHTML = actions.map(a => '<li>'+esc(a)+'</li>').join(''); }
  function renderEvents(registry, alerts, summary, observability){ const target = $('command-v2-event-list'); if(!target) return; const discovered = sites(registry).filter(s => !isMonitored(s)).length; const monitored = sites(registry).filter(isMonitored).length; const ac = alertCount(alerts); const r = summary.runtime || {}; const events = [];
    events.push('Runtime status: ' + esc(runtimeStatus(summary)) + (r.last_finished_at_utc ? ' at ' + esc(r.last_finished_at_utc) : ''));
    events.push('Registry coverage: ' + monitored + ' monitored, ' + discovered + ' discovered.');
    events.push('Alert feed: ' + ac + ' active alert(s).');
    events.push('Observability records: ' + arr(observability.runtime_history).length + ' runtime history item(s).');
    target.innerHTML = events.map(e => '<li>'+e+'</li>').join(''); }
  function setSummary({registry, alerts, summary, sourceState, footprint}){ const discovered = sites(registry).filter(s => !isMonitored(s)).length; const ac = alertCount(alerts); const score = healthScore({registry, alerts, summary, sourceState}); const gov = String(footprint.safe_to_show_named_access_ui ?? footprint.source_status ?? 'available'); const reportState = 'Ready'; let posture = 'Healthy'; if(ac || discovered) posture = 'Review'; set('command-v2-health-score', score + '%'); set('command-v2-posture', posture); set('command-v2-posture-note', discovered + ' discovery item(s), ' + ac + ' active alert(s).'); set('command-v2-discovery-pressure', discovered); set('command-v2-governance-readiness', gov); set('command-v2-report-readiness', reportState); }
  async function init(){ if(!document.querySelector('.command-intelligence-v2')) return; try{ const [summary, alerts, registry, footprint, sourceState, observability] = await Promise.all([ json('/operator/summary').catch(()=>({})), json('/operator/alerts').catch(()=>({})), json('/registry/sites').catch(()=>({})), json('/users/footprint').catch(()=>({})), json('/api/source-state').catch(()=>({})), json('/operator/observability').catch(()=>({})) ]); setSummary({registry, alerts, summary, sourceState, footprint}); renderRisks(registry, alerts, summary, sourceState); renderActions(registry, footprint, alerts, summary); renderEvents(registry, alerts, summary, observability); const diag = $('command-v2-diagnostics-json'); if(diag) diag.textContent = JSON.stringify({generated_at:new Date().toISOString(), health_score: healthScore({registry, alerts, summary, sourceState}), registry_summary: registry.summary || {}, alert_count: alertCount(alerts), runtime: summary.runtime || {}, users_analyzed: userCount(footprint), assignments: assignmentCount(footprint)}, null, 2); }catch(error){ set('command-v2-posture','Review'); const target = $('command-v2-action-list'); if(target) target.innerHTML = '<li>Command intelligence v2 failed to load: '+esc(error.message)+'</li>'; } }
  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();

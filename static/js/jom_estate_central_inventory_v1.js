(function(){
  'use strict';
  if((document.body.getAttribute('data-jom-page') || '') !== 'estate') return;
  const $ = id => document.getElementById(id);
  const set = (id, value) => { const el=$(id); if(el) el.textContent = String(value ?? 0); };
  const norm = value => String(value || '').trim().toLowerCase();
  async function getJson(url){
    try { const res = await fetch(url, {cache:'no-store'}); if(!res.ok) return null; return await res.json(); }
    catch(_error){ return null; }
  }
  function siteKey(site){ return String(site.site_key || site.key || site.site_name || site.name || '').trim(); }
  function siteLifecycle(site, decisions){
    const key = siteKey(site);
    const decision = decisions[key] || decisions[norm(key)] || {};
    const d = norm(decision.decision);
    if(d === 'approve') return 'approval_pending';
    if(d === 'monitored') return 'monitored';
    if(d === 'ignore') return 'ignored';
    if(d === 'discovered') return 'discovered';
    const c = norm(site.classification || site.lifecycle || site.status);
    if(c.includes('monitor')) return 'monitored';
    if(c.includes('ignore')) return 'ignored';
    if(c.includes('approval') || c.includes('pending')) return 'approval_pending';
    if(c.includes('discover')) return 'discovered';
    return c || 'unknown';
  }
  function isCriticalSite(site, alerts){
    const key = norm(siteKey(site));
    return alerts.some(alert => {
      const text = JSON.stringify(alert || {}).toLowerCase();
      return key && text.includes(key) && (text.includes('critical') || text.includes('high'));
    });
  }
  function isDegradedSite(site, alerts){
    const key = norm(siteKey(site));
    const health = norm(site.health || site.status || site.source_state || site.operational_state);
    if(health.includes('degraded') || health.includes('review') || health.includes('warning')) return true;
    return alerts.some(alert => {
      const text = JSON.stringify(alert || {}).toLowerCase();
      return key && text.includes(key) && (text.includes('degraded') || text.includes('warning') || text.includes('review'));
    });
  }
  function setCardState(id, value, state){
    set(id, value);
    const card = $(id) && $(id).closest('.estate-overview-card');
    if(card && state) card.setAttribute('data-state', state);
  }
  async function refreshOverview(){
    const registry = await getJson('/api/site-registry') || await getJson('/registry/sites') || {};
    const decisionsPayload = await getJson('/api/site-lifecycle/decisions') || {};
    const alertsPayload = await getJson('/operator/alerts') || {};
    const sites = Array.isArray(registry.sites) ? registry.sites : [];
    const decisions = decisionsPayload.decisions || {};
    const alerts = Array.isArray(alertsPayload.alerts) ? alertsPayload.alerts : [];
    const counts = { total: sites.length, monitored:0, discovered:0, pending:0, ignored:0, degraded:0, critical:0 };
    sites.forEach(site => {
      const lifecycle = siteLifecycle(site, decisions);
      if(lifecycle === 'monitored') counts.monitored += 1;
      else if(lifecycle === 'ignored') counts.ignored += 1;
      else if(lifecycle === 'approval_pending') counts.pending += 1;
      else if(lifecycle === 'discovered') counts.discovered += 1;
      if(isCriticalSite(site, alerts)) counts.critical += 1;
      else if(isDegradedSite(site, alerts)) counts.degraded += 1;
    });
    setCardState('estate-overview-total', counts.total, 'ok');
    setCardState('estate-overview-monitored', counts.monitored, 'ok');
    setCardState('estate-overview-discovered', counts.discovered, counts.discovered ? 'warn' : 'ok');
    setCardState('estate-overview-pending', counts.pending, counts.pending ? 'warn' : 'ok');
    setCardState('estate-overview-ignored', counts.ignored, 'ok');
    setCardState('estate-overview-degraded', counts.degraded, counts.degraded ? 'warn' : 'ok');
    setCardState('estate-overview-critical', counts.critical, counts.critical ? 'critical' : 'ok');
  }
  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', refreshOverview); else refreshOverview();
  setTimeout(refreshOverview, 1000);
  setTimeout(refreshOverview, 3000);
})();

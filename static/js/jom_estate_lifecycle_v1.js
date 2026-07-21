(function(){
  'use strict';
  const $ = id => document.getElementById(id);
  const arr = value => Array.isArray(value) ? value : [];
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const setText = (id, value) => { const el = $(id); if (el) el.textContent = String(value ?? '--'); };
  async function fetchJson(url){ const r = await fetch(url,{cache:'no-store'}); if(!r.ok) throw new Error(url+' '+r.status); return r.json(); }
  function siteKey(site){ return site.site_key || site.key || site.site_name || site.name || 'unknown-site'; }
  function siteName(site){ return site.site_name || site.name || siteKey(site); }
  function siteUrl(site){ return site.site_url || site.url || ''; }
  function textBlob(site){ return [site.classification,site.monitoring_status,site.monitoring_state,site.lifecycle_state,site.status,site.state,site.decision,site.policy_state].join(' ').toLowerCase(); }
  function isMonitored(site){ const text=textBlob(site); return site.monitored===true || site.is_monitored===true || site.in_monitoring_scope===true || text.includes('monitored') || text.includes('monitoring enabled'); }
  function isPending(site){ return textBlob(site).includes('pending'); }
  function isRetired(site){ const text=textBlob(site); return text.includes('retired') || text.includes('suspended'); }
  function decisionFor(site, decisions){ return (decisions && decisions[siteKey(site)]) || {}; }
  function decisionValue(site, decisions){ return String(decisionFor(site, decisions).decision || '').toLowerCase(); }
  function lifecycle(site, decisions){
    const d=decisionValue(site, decisions);
    if(d==='approve') return 'Approval Pending';
    if(d==='ignore') return 'Ignored';
    if(d==='pending') return 'Pending Review';
    if(isRetired(site)) return 'Retired';
    if(isPending(site)) return 'Approval Pending';
    if(isMonitored(site)) return 'Monitored';
    return 'Discovered';
  }
  function monitoring(site, decisions){
    const d=decisionValue(site, decisions);
    if(d==='approve') return 'Credential required';
    if(d==='ignore') return 'Ignored';
    return isMonitored(site) ? 'Enabled' : 'Not monitored';
  }
  function health(site, decisions){
    const life=lifecycle(site, decisions).toLowerCase();
    if(life.includes('monitored')) return 'Healthy';
    if(life.includes('ignored')) return 'Inactive';
    if(life.includes('approval')) return 'Pending';
    if(life.includes('retired')) return 'Retired';
    return 'Review';
  }
  function owner(site){ return site.owner || site.business_owner || site.technical_owner || 'Unassigned'; }
  function lastObservation(site){ return site.last_observation || site.last_seen || site.updated_at || 'Live registry'; }
  function pillClass(value){ const lower=String(value).toLowerCase(); if(lower.includes('monitored')||lower.includes('healthy')||lower==='enabled') return 'estate-status-pill estate-status-pill--ok'; if(lower.includes('retired')||lower.includes('ignored')||lower.includes('inactive')) return 'estate-status-pill estate-status-pill--retired'; return 'estate-status-pill estate-status-pill--review'; }
  function actionHref(site){ return isMonitored(site) ? `/site/${encodeURIComponent(siteKey(site))}` : `/estate/review/${encodeURIComponent(siteKey(site))}`; }
  function actionLabel(site, decisions){ const life=lifecycle(site, decisions); if(life==='Approval Pending') return 'Continue Review'; if(life==='Ignored') return 'Restore / Review'; return isMonitored(site) ? 'Open Workspace' : 'Review Site'; }
  function reviewItem(site){ return `<article class="estate-review-item"><div><strong>${esc(siteName(site))}</strong><br><small>${esc(siteUrl(site) || siteKey(site))}</small><br><span>Source: ${esc(Array.isArray(site.sources) ? site.sources.join(', ') : (site.source || 'Registry'))}</span></div><a class="estate-action-link" href="${actionHref(site)}">Review Site</a></article>`; }
  function registryRow(site, decisions){
    const life=lifecycle(site, decisions), mon=monitoring(site, decisions), h=health(site, decisions);
    const nameHtml = siteUrl(site) ? `<a class="estate-site-link estate-site-link--button" href="${esc(siteUrl(site))}" target="_blank" rel="noopener" aria-label="Open ${esc(siteName(site))} in a new browser tab"><span>${esc(siteName(site))}</span><span aria-hidden="true" class="estate-external-icon">↗</span></a>` : `<strong>${esc(siteName(site))}</strong>`;
    return `<tr><td>${nameHtml}</td><td><span class="${pillClass(life)}">${esc(life)}</span></td><td><span class="${pillClass(mon)}">${esc(mon)}</span></td><td><span class="${pillClass(h)}">${esc(h)}</span></td><td>${esc(owner(site))}</td><td>${esc(lastObservation(site))}</td><td><a class="estate-action-link" href="${actionHref(site)}">${actionLabel(site, decisions)}</a></td></tr>`;
  }
  function bucketSites(sites, decisions){
    const monitored=sites.filter(s => isMonitored(s) && !isRetired(s));
    const approval=sites.filter(s => decisionValue(s,decisions)==='approve' || (isPending(s) && decisionValue(s,decisions)!=='ignore'));
    const ignored=sites.filter(s => decisionValue(s,decisions)==='ignore');
    const retired=sites.filter(isRetired);
    const review=sites.filter(s => !isMonitored(s) && !isPending(s) && !isRetired(s) && !['approve','ignore'].includes(decisionValue(s,decisions)));
    const critical=sites.filter(s => textBlob(s).includes('critical'));
    return {monitored, approval, ignored, retired, review, critical};
  }
  function renderRegistry(sites, decisions){
    const body=$('estate-registry-body'); if(!body) return;
    const search=($('estate-search')?.value||'').toLowerCase().trim(); const filter=$('estate-filter')?.value||'all';
    let visible=sites.slice();
    if(filter!=='all'){
      visible=visible.filter(site => {
        const life=lifecycle(site, decisions).toLowerCase();
        if(filter==='monitored') return life==='monitored';
        if(filter==='discovered') return life==='discovered' || life==='pending review';
        if(filter==='pending') return life==='approval pending';
        if(filter==='retired') return life==='retired' || life==='ignored';
        return true;
      });
    }
    if(search){ visible=visible.filter(site => [siteName(site),siteKey(site),siteUrl(site),lifecycle(site,decisions),monitoring(site,decisions),health(site,decisions),owner(site)].join(' ').toLowerCase().includes(search)); }
    body.innerHTML=visible.length ? visible.map(site=>registryRow(site, decisions)).join('') : '<tr><td colspan="7">No sites match the current filter.</td></tr>';
  }
  function countUsers(payload){ if(Array.isArray(payload.users)) return payload.users.length; if(Array.isArray(payload.rows)) return payload.rows.length; return payload.user_count || payload.total_users || payload.summary?.users_analyzed || payload.summary?.named_unique_users || 'n/a'; }
  async function init(){
    const [registryResult, usersResult, alertsResult, sourceResult, decisionsResult] = await Promise.allSettled([fetchJson('/registry/sites'), fetchJson('/users/footprint'), fetchJson('/operator/alerts'), fetchJson('/api/source-state'), fetchJson('/api/site-lifecycle/decisions')]);
    const registry=registryResult.status==='fulfilled'?registryResult.value:{}; const users=usersResult.status==='fulfilled'?usersResult.value:{}; const alerts=alertsResult.status==='fulfilled'?alertsResult.value:{}; const sourceOk=sourceResult.status==='fulfilled';
    const decisionPayload=decisionsResult.status==='fulfilled'?decisionsResult.value:{}; const decisions=decisionPayload.decisions||{}; const sites=arr(registry.sites); const b=bucketSites(sites, decisions); const alertsCount=Number(alerts.count ?? (Array.isArray(alerts.alerts)?alerts.alerts.length:0))||0; const userCount=countUsers(users);
    setText('estate-total-sites', sites.length); setText('estate-monitored-sites', b.monitored.length); setText('estate-discovered-sites', b.review.length); setText('estate-pending-sites', b.approval.length); setText('estate-critical-sites', b.critical.length); setText('estate-retired-sites', b.retired.length); setText('estate-review-count', `${b.review.length} review`);
    setText('rail-total-sites', sites.length); setText('rail-monitored-sites', b.monitored.length); setText('rail-discovered-sites', b.review.length); setText('rail-review-queue', b.review.length); setText('rail-pending-sites', b.approval.length); setText('rail-retired-sites', b.retired.length); setText('rail-registry-status', sourceOk?'OK':'Review'); setText('rail-users-count', userCount); setText('rail-alert-count', alertsCount);
    const reviewList=$('estate-review-list'); if(reviewList){ reviewList.innerHTML=b.review.length ? b.review.map(reviewItem).join('') : '<p class="estate-empty">No discovered sites currently require review.</p>'; }
    renderRegistry(sites, decisions); $('estate-search')?.addEventListener('input',()=>renderRegistry(sites,decisions)); $('estate-filter')?.addEventListener('change',()=>renderRegistry(sites,decisions));
  }
  document.addEventListener('DOMContentLoaded',()=>init().catch(error=>{ console.error('Estate lifecycle sync failed', error); const body=$('estate-registry-body'); if(body) body.innerHTML='<tr><td colspan="7">Unable to load estate registry data.</td></tr>'; }));
})();

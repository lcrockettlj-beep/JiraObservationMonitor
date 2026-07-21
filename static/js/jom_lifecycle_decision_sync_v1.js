(function(){
  'use strict';
  const arr=v=>Array.isArray(v)?v:[];
  const setText=(id,v)=>{const el=document.getElementById(id); if(el) el.textContent=String(v);};
  const esc=v=>String(v??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  async function fetchJson(url){const r=await fetch(url,{cache:'no-store'}); if(!r.ok) throw new Error(url+' '+r.status); return r.json();}
  function key(site){return site.site_key||site.key||site.site_name||site.name||'unknown-site';}
  function textBlob(site){return [site.classification,site.monitoring_status,site.monitoring_state,site.lifecycle_state,site.status,site.state,site.decision,site.policy_state].join(' ').toLowerCase();}
  function isMonitored(site){const t=textBlob(site); return site.monitored===true||site.is_monitored===true||site.in_monitoring_scope===true||t.includes('monitored')||t.includes('monitoring enabled');}
  function isPending(site){return textBlob(site).includes('pending');}
  function isRetired(site){const t=textBlob(site); return t.includes('retired')||t.includes('suspended');}
  function decision(site, decisions){return String((decisions[key(site)]||{}).decision||'').toLowerCase();}
  function card(o){return `<article class="jom-risk-item"><div class="jom-risk-item__top"><div class="jom-risk-title">${esc(o.title)}</div><span class="jom-risk-badge">${esc(o.badge)}</span></div><div class="jom-risk-row"><span>Impact</span><div>${esc(o.impact)}</div></div><div class="jom-risk-row"><span>Action</span><div>${esc(o.action)}</div></div><div class="jom-risk-row"><span>Fix location</span><div>${esc(o.location)}</div></div><a class="jom-button" href="${esc(o.href)}">Open</a></article>`;}
  async function init(){
    if(document.body.getAttribute('data-jom-page')!=='command-centre') return;
    const [regResult, decisionsResult, alertsResult] = await Promise.allSettled([fetchJson('/registry/sites'), fetchJson('/api/site-lifecycle/decisions'), fetchJson('/operator/alerts')]);
    const registry=regResult.status==='fulfilled'?regResult.value:{}; const decisions=(decisionsResult.status==='fulfilled'?decisionsResult.value.decisions:{})||{}; const alerts=alertsResult.status==='fulfilled'?alertsResult.value:{}; const sites=arr(registry.sites);
    const monitored=sites.filter(s=>isMonitored(s)&&!isRetired(s));
    const review=sites.filter(s=>!isMonitored(s)&&!isPending(s)&&!isRetired(s)&&!['approve','ignore'].includes(decision(s,decisions)));
    const approval=sites.filter(s=>decision(s,decisions)==='approve' || (isPending(s)&&decision(s,decisions)!=='ignore'));
    const actionableAlerts=arr(alerts.alerts).filter(a=>['warning','warn','critical','error','risk'].includes(String(a.level||'').toLowerCase()));
    const risks=review.length+approval.length+actionableAlerts.length;
    setText('jom-rail-review-items', risks);
    setText('jom-final-active-risks', risks);
    setText('jom-rail-coverage-reason', `${monitored.length} monitored - ${review.length} awaiting review`);
    const list=document.getElementById('jom-final-risk-list'); if(!list) return;
    const cards=[];
    actionableAlerts.forEach(alert=>cards.push(card({title:alert.title||'Actionable alert requires review',badge:String(alert.level||'Risk'),impact:alert.reason||'An operator alert requires review.',action:alert.recommended_action||'Review the alert context.',location:alert.source?`Source: ${alert.source}`:'System - Runtime Status',href:'/operator/observability'})));
    if(review.length) cards.push(card({title:'Discovery backlog awaiting review',badge:'Review',impact:`${review.length} site(s) are known but not yet governed.`,action:'Review discovered sites and decide whether to monitor, ignore, or keep pending.',location:'Estate - Discovered Sites',href:'/estate#discovered-sites'}));
    if(approval.length) cards.push(card({title:'Monitoring approval pending credentials',badge:'Approval Pending',impact:`${approval.length} site(s) have been approved but still require credential/token enablement.`,action:'Complete credential onboarding before monitoring can start.',location:'Estate - Site Review',href:'/estate#site-registry'}));
    if(!cards.length) cards.push(card({title:'No immediate operational risks detected',badge:'OK',impact:'No active alert, discovery backlog, or approval-pending credential task requires immediate review.',action:'Continue monitoring estate health and source freshness.',location:'Command Centre',href:'/'}));
    list.innerHTML=cards.join('');
  }
  document.addEventListener('DOMContentLoaded',()=>setTimeout(()=>init().catch(err=>console.warn('Lifecycle decision sync failed',err)),350));
})();

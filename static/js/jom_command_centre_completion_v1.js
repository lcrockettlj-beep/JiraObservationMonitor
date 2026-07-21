(function(){
  'use strict';
  const $=id=>document.getElementById(id);
  const arr=v=>Array.isArray(v)?v:[];
  const esc=v=>String(v??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  async function fetchJson(url){const r=await fetch(url,{cache:'no-store'});if(!r.ok)throw new Error(url+' '+r.status);return r.json()}
  function regCounts(reg){
    const s=reg?.summary||{},sites=arr(reg?.sites);
    const total=Number(s.total_sites??s.total??sites.length??0)||0;
    let monitored=Number(s.monitored_count??s.monitored_sites??s.in_scope_count);
    let discovered=Number(s.discovered_count??s.pending_onboarding_count??s.unmonitored_count??s.awaiting_review_count);
    if(!Number.isFinite(monitored)){
      monitored=sites.filter(site=>{
        const text=[site.classification,site.monitoring_status,site.monitoring_state,site.lifecycle_state,site.status,site.state,site.decision,site.policy_state].join(' ').toLowerCase();
        return site.monitored===true||site.is_monitored===true||site.in_monitoring_scope===true||text.includes('monitored')||text.includes('monitoring enabled')
      }).length
    }
    if(!Number.isFinite(discovered)){discovered=Math.max(total-monitored,0)}
    return{total,monitored,discovered,sites}
  }
  function actionableAlerts(alerts){
    return arr(alerts?.alerts).filter(a=>{
      const level=String(a?.level||'').toLowerCase();
      return level==='warning'||level==='warn'||level==='critical'||level==='error'||level==='risk';
    });
  }
  function sourceHealth(summary,source){
    const t=JSON.stringify({summary:summary?.source_health,source:source?.source_reliability}).toLowerCase();
    if(t.includes('fail')||t.includes('critical')||t.includes('error'))return'Review';
    if(t.includes('warn')||t.includes('stale'))return'Check';
    return'Healthy'
  }
  function setText(id,v){const n=$(id);if(n)n.textContent=v}
  function setHtml(id,v){const n=$(id);if(n)n.innerHTML=v}
  function riskCard(o){return `<article class="jom-risk-item"><div class="jom-risk-item__top"><div class="jom-risk-title">${esc(o.title)}</div><span class="jom-risk-badge">${esc(o.badge)}</span></div><div class="jom-risk-row"><span>Impact</span><div>${esc(o.impact)}</div></div><div class="jom-risk-row"><span>Action</span><div>${esc(o.action)}</div></div><div class="jom-risk-row"><span>Fix location</span><div>${esc(o.location)}</div></div><a class="jom-button" href="${esc(o.href)}">Open</a></article>`}
  function actionItem(t,x,h){return `<li><strong>${esc(t)}</strong><span>${esc(x)}</span><a class="jom-button" href="${esc(h)}">Open</a></li>`}
  function tile(t,p,x,k){const c=k==='ok'?'jom-pill--ok':k==='risk'?'jom-pill--risk':k==='warn'?'jom-pill--warn':'';return `<div class="jom-status-tile"><strong>${esc(t)} <span class="jom-pill ${c}">${esc(p)}</span></strong><span>${esc(x)}</span></div>`}
  async function init(){
    const [summary,alerts,registry,users,sourceState,execReport]=await Promise.allSettled([fetchJson('/operator/summary'),fetchJson('/operator/alerts'),fetchJson('/registry/sites'),fetchJson('/users/footprint'),fetchJson('/api/source-state'),fetch('/reports/generated/executive/html',{cache:'no-store'})]);
    const sj=summary.status==='fulfilled'?summary.value:{};
    const aj=alerts.status==='fulfilled'?alerts.value:{};
    const rj=registry.status==='fulfilled'?registry.value:{};
    const uj=users.status==='fulfilled'?users.value:{};
    const src=sourceState.status==='fulfilled'?sourceState.value:{};
    const reportsOk=execReport.status==='fulfilled'&&execReport.value&&execReport.value.ok;
    const rc=regCounts(rj);
    const riskAlerts=actionableAlerts(aj);
    const actionableAlertCount=riskAlerts.length;
    const runtime=sj.runtime||{};
    const runtimeStatus=String(runtime.last_result_status||runtime.state||sj.posture||'ok');
    const runtimeOk=!/fail|error|critical/i.test(runtimeStatus);
    const dataHealth=sourceHealth(sj,src);
    const us=uj.summary||{};
    const usersAnalysed=Number(us.users_analyzed??us.named_unique_users??0)||0;
    const reviewItems=rc.discovered>0?1:0;
    const risks=actionableAlertCount+reviewItems;
    let health=100;
    if(!runtimeOk)health-=25;
    health-=Math.min(actionableAlertCount*15,30);
    health-=Math.min(rc.discovered*4,24);
    if(rc.monitored===0)health-=15;
    if(!reportsOk)health-=5;
    health=Math.max(0,Math.min(100,Math.round(health)));
    setText('jom-final-health-score',health+'%');
    const bar=$('jom-final-health-bar');if(bar)bar.style.width=health+'%';
    setText('jom-final-health-reason',`Calculated from runtime ${runtimeOk?'ok':'requiring review'}, ${actionableAlertCount} actionable alert(s), ${rc.monitored} monitored site(s), and ${rc.discovered} site(s) awaiting review.`);
    setText('jom-final-total-sites',rc.total);
    setText('jom-final-estate-subtext',`${rc.monitored} monitored - ${rc.discovered} awaiting review`);
    setText('jom-final-monitored-sites',rc.monitored);
    setText('jom-final-active-risks',risks);
    setText('jom-final-data-health',dataHealth);
    const risksHtml=[];
    riskAlerts.forEach(alert=>risksHtml.push(riskCard({
      title:alert.title||'Actionable alert requires review',
      badge:String(alert.level||'Risk'),
      impact:alert.reason||'An operator alert requires review before stakeholder output is shared.',
      action:alert.recommended_action||'Review the alert context and confirm whether operational action is required.',
      location:alert.source?`Source: ${alert.source}`:'System - Runtime Status',
      href:'/operator/observability'
    })));
    if(rc.discovered>0)risksHtml.push(riskCard({title:'Discovery backlog awaiting review',badge:'Review',impact:`${rc.discovered} site(s) are known but not yet governed.`,action:'Review discovered sites and decide whether to monitor, reject, or keep pending.',location:'Admin - Discovery Queue',href:'/reference'}));
    if(!risksHtml.length)risksHtml.push(riskCard({title:'No immediate operational risks detected',badge:'OK',impact:'No actionable alert or discovery backlog requires immediate review.',action:'Continue monitoring estate health and source freshness.',location:'Command Centre',href:'/'}));
    setHtml('jom-final-risk-list',risksHtml.join(''));
    const actions=[];
    riskAlerts.slice(0,1).forEach(alert=>actions.push(actionItem(alert.title||'Review actionable alert',alert.recommended_action||'Confirm alert impact before stakeholder output is shared.','/operator/observability')));
    if(rc.discovered>0)actions.push(actionItem('Review discovery backlog',`${rc.discovered} discovered site(s) need an Admin review decision.`,'/reference'));
    actions.push(actionItem('Inspect monitored estate','Use Estate to select a site and open Site Workspace when investigation is needed.','/estate'));
    setHtml('jom-final-action-list',actions.slice(0,3).join(''));
    setHtml('jom-final-status-list',[tile('Runtime',runtimeOk?'ok':'review',`operator runtime contract reports ${runtimeStatus}.`,runtimeOk?'ok':'warn'),tile('Registry',`${rc.monitored} monitored`,`${rc.discovered} awaiting review`,rc.discovered?'warn':'ok'),tile('Alerts',`${actionableAlertCount} actionable`,'warning/critical operator alert feed',actionableAlertCount?'risk':'ok'),tile('Users',`${usersAnalysed||'n/a'}`,'users analysed by footprint source','ok')].join(''));
    setText('jom-final-discovery-summary',`${rc.discovered} site(s) require review before monitoring decisions are complete.`)
  }
  document.addEventListener('DOMContentLoaded',()=>{init().catch(err=>{console.error('Command Centre completion failed',err);setHtml('jom-final-risk-list',riskCard({title:'Command Centre data unavailable',badge:'Review',impact:'The browser could not load one or more live operator contracts.',action:'Check JOM runtime and source health before using Command Centre output.',location:'System - Runtime Status',href:'/health'}));setHtml('jom-final-action-list',actionItem('Check runtime status','Confirm the application and operator endpoints are responding.','/health'))})})
})();
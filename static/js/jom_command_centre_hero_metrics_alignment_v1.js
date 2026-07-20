(function(){
  'use strict';
  function num(v){ return Number.isFinite(Number(v)) ? Number(v) : 0; }
  function pct(a,b){ return b ? Math.round((a/b)*100) : 0; }
  function setText(id, value){ var el=document.getElementById(id); if(el){ el.textContent=String(value); } }
  async function getJson(url){ var r=await fetch(url,{cache:'no-store'}); if(!r.ok){ throw new Error(url+' '+r.status); } return await r.json(); }
  function counts(reg){
    var s=(reg&&reg.summary)||{};
    var sites=Array.isArray(reg&&reg.sites)?reg.sites:[];
    var total=num(s.total_sites||s.total||sites.length);
    var monitored=num(s.monitored_count||s.monitored_sites||s.in_scope_count);
    var discovered=num(s.discovered_count||s.pending_onboarding_count||s.unmonitored_count||s.awaiting_review_count);
    if(!monitored && sites.length){ monitored=sites.filter(function(site){ var tokens=[site.classification,site.monitoring_status,site.monitoring_state,site.lifecycle_state,site.status,site.state,site.decision,site.policy_state].join(' ').toLowerCase(); return site.monitored===true || site.in_monitoring_scope===true || tokens.indexOf('monitored')>=0 || tokens.indexOf('monitoring enabled')>=0; }).length; }
    if(!discovered && total){ discovered=Math.max(total-monitored,0); }
    return {total:total, monitored:monitored, discovered:discovered, coverage:pct(monitored,total)};
  }
  function removeStrandedCoverage(){ document.querySelectorAll('[data-jom-semantic="coverage-card"], .jom-coverage-card.jom-metric-card, .jom-monitoring-coverage-card').forEach(function(el){ if(!el.closest('.jom-hero-metric-pair')){ el.remove(); } }); }
  async function run(){ try{ var reg=await getJson('/registry/sites'); var c=counts(reg); var review=Math.max(c.total-c.monitored,0); setText('jom-final-monitoring-coverage', c.coverage+'%'); setText('jom-final-coverage-reason', c.monitored+' monitored - '+review+' awaiting review'); var mon=document.getElementById('jom-final-coverage-monitored'); var rev=document.getElementById('jom-final-coverage-review'); if(mon){ mon.style.width=c.coverage+'%'; } if(rev){ rev.style.width=(100-c.coverage)+'%'; } removeStrandedCoverage(); }catch(e){ console.warn('Monitoring coverage hero alignment failed', e); } }
  if(document.readyState==='loading'){ document.addEventListener('DOMContentLoaded', run); } else { run(); }
  window.setTimeout(run, 500); window.setTimeout(removeStrandedCoverage, 1200);
})();

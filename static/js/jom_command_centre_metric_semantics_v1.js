(function(){
  'use strict';
  function num(v){ return Number.isFinite(Number(v)) ? Number(v) : 0; }
  function setText(sel, val){ document.querySelectorAll(sel).forEach(function(el){ el.textContent = String(val); }); }
  function pct(a,b){ return b ? Math.round((a/b)*100) : 0; }
  async function getJson(url){ const r = await fetch(url, {cache:'no-store'}); if(!r.ok) throw new Error(url+' '+r.status); return await r.json(); }
  function getRegistryCounts(reg){
    const s = reg && reg.summary ? reg.summary : {};
    const sites = Array.isArray(reg && reg.sites) ? reg.sites : [];
    let total = num(s.total_sites || s.total || sites.length);
    let monitored = num(s.monitored_count || s.monitored_sites || 0);
    let discovered = num(s.discovered_count || s.pending_onboarding_count || 0);
    if(!monitored && sites.length){
      monitored = sites.filter(function(site){
        const fields=[site.monitoring_status, site.status, site.state, site.classification, site.registry_state, site.monitoring];
        return fields.some(function(v){ return String(v || '').toLowerCase().includes('monitored'); });
      }).length;
    }
    if(!discovered && total){ discovered = Math.max(total - monitored, 0); }
    return {total: total, monitored: monitored, discovered: discovered, coverage: pct(monitored,total), unmonitored: total ? 100-pct(monitored,total) : 0};
  }
  function readinessScore(counts, alerts, runtimeOk, dataOk){
    let score=100;
    if(!runtimeOk) score -= 25;
    if(!dataOk) score -= 15;
    score -= Math.min(num(alerts)*8, 24);
    score -= Math.min(counts.discovered*4, 20);
    if(counts.total && counts.coverage < 50) score -= 8;
    return Math.max(0, Math.min(100, Math.round(score)));
  }
  function updateHealthCard(counts, alerts, runtimeOk, dataOk){
    const score = readinessScore(counts, alerts, runtimeOk, dataOk);
    Array.from(document.querySelectorAll('h2,h3,p,span,strong')).filter(function(el){ return /estate health/i.test(el.textContent || ''); }).forEach(function(el){ el.textContent = (el.textContent || '').replace(/Estate Health/i, 'Operational Readiness'); });
    setText('[data-jom-command="estate-health"], #jom-estate-health, [data-jom-final="estate-health"]', score + '%');
    const note = 'Calculated from runtime health, data/source availability, active risk count, and monitoring coverage. Monitored-site health should be treated separately from estate coverage.';
    document.querySelectorAll('[data-jom-command="estate-health-note"], #jom-estate-health-note, [data-jom-final="health-note"]').forEach(function(el){ el.textContent = note; });
    setText('[data-jom-command="monitored"], #jom-monitored-sites, [data-jom-final="monitored"]', counts.monitored);
    setText('[data-jom-command="total-sites"], #jom-total-sites, [data-jom-final="total-sites"]', counts.total);
    setText('[data-jom-command="discovered"], #jom-discovered-sites, [data-jom-final="discovered"]', counts.discovered);
    setText('[data-jom-command="coverage"], #jom-monitoring-coverage, [data-jom-final="coverage"]', counts.coverage + '%');
    const hero = document.querySelector('.jom-hero, .jom-command-hero, .command-hero, main');
    if(hero && !document.querySelector('[data-jom-semantic="score-explainer"]')){
      const box=document.createElement('div'); box.className='jom-score-explainer'; box.setAttribute('data-jom-semantic','score-explainer');
      box.innerHTML='<h3>What this score means</h3><p><strong>Operational Readiness</strong> combines JOM runtime status, data/source availability, active risks, monitoring coverage and discovery backlog. <strong>Monitoring Coverage</strong> is shown separately: '+counts.monitored+' of '+counts.total+' site(s) are monitored ('+counts.coverage+'%).</p>';
      hero.appendChild(box);
    }
  }
  function addCoverageCard(counts){
    const metricArea = document.querySelector('.jom-metrics, .jom-final-metrics, .metrics-grid, [data-jom-zone="metrics"]');
    if(!metricArea || document.querySelector('[data-jom-semantic="coverage-card"]')) return;
    const card=document.createElement('article'); card.className='jom-card jom-metric-card jom-coverage-card'; card.setAttribute('data-jom-semantic','coverage-card');
    card.innerHTML='<p class="jom-kicker">Monitoring Coverage</p><h2>'+counts.coverage+'%</h2><div class="jom-coverage-bar"><span style="width:'+counts.coverage+'%"></span><span style="width:'+counts.unmonitored+'%"></span></div><p class="jom-semantic-metric-note">'+counts.monitored+' monitored · '+counts.discovered+' awaiting review</p>';
    metricArea.appendChild(card);
  }
  async function run(){
    try{
      const reg = await getJson('/registry/sites');
      const summary = await getJson('/operator/summary');
      const alerts = await getJson('/operator/alerts');
      const source = await getJson('/api/source-state').catch(function(){return {};});
      const counts = getRegistryCounts(reg);
      const alertCount = num(alerts.count || (Array.isArray(alerts.alerts)?alerts.alerts.length:0));
      const runtime = summary && summary.runtime ? summary.runtime : {};
      const runtimeOk = String(runtime.last_result_status || runtime.status || 'ok').toLowerCase().includes('ok') || String(runtime.state || '').toLowerCase()==='idle';
      const dataOk = !!source || !!summary.source_health;
      updateHealthCard(counts, alertCount, runtimeOk, dataOk);
      addCoverageCard(counts);
    }catch(e){ console.warn('JOM command metric semantics update failed', e); }
  }
  if(document.readyState==='loading'){ document.addEventListener('DOMContentLoaded', run); } else { run(); }
})();

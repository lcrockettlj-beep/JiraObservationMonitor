(function(){
  'use strict';
  const $=id=>document.getElementById(id);
  const arr=v=>Array.isArray(v)?v:[];
  const esc=v=>String(v??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  async function fetchJson(url){const r=await fetch(url,{cache:'no-store'});if(!r.ok)throw new Error(url+' '+r.status);return r.json()} function unwrapContract(payload){if(payload&&typeof payload==='object'&&payload.data&&typeof payload.data==='object')return payload.data;return payload||{}} function unwrapSourceState(payload){return payload||{}} function userCount(payload){const p=payload||{};const s=p.summary||{};return Number(s.users_analyzed??s.named_unique_users??s.user_count??s.total_users??p.user_count??p.total_users??(Array.isArray(p.users)?p.users.length:0)??(Array.isArray(p.rows)?p.rows.length:0)??0)||0}
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
    const rj=registry.status==='fulfilled'?unwrapContract(registry.value):{};
    const uj=users.status==='fulfilled'?unwrapContract(users.value):{};
    const src=sourceState.status==='fulfilled'?unwrapSourceState(sourceState.value):{};
    const reportsOk=execReport.status==='fulfilled'&&execReport.value&&execReport.value.ok;
    const rc=regCounts(rj);
    const riskAlerts=actionableAlerts(aj);
    const actionableAlertCount=riskAlerts.length;
    const runtime=sj.runtime||{};
    let runtimeStatus=String(runtime.last_result_status||runtime.state||sj.posture||'ok'); if(!runtimeStatus||runtimeStatus.toLowerCase()==='unknown'||runtimeStatus.toLowerCase()==='null'){runtimeStatus='ok';}
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
const coveragePct = rc.total ? Math.round((rc.monitored / rc.total) * 100) : 0;
setText('jom-rail-monitoring-coverage', coveragePct + '%');
setText('jom-rail-coverage-reason', `${rc.monitored} monitored - ${Math.max(rc.total-rc.monitored,0)} awaiting review`);
setText('jom-rail-total-sites', rc.total);
setText('jom-rail-monitored-sites', rc.monitored);
setText('jom-rail-review-items', risks);
setText('jom-rail-data-health', dataHealth);
setText('jom-rail-runtime', runtimeOk ? 'OK' : 'Review');
setText('jom-rail-alerts', actionableAlertCount);
setText('jom-rail-users', usersAnalysed || 'n/a');
const railRing = document.querySelector('.jom-coverage-ring');
if (railRing) { railRing.style.setProperty('--coverage-deg', (coveragePct * 3.6) + 'deg'); }
const railMon = document.getElementById('jom-rail-coverage-monitored');
const railRev = document.getElementById('jom-rail-coverage-review');
if (railMon) { railMon.style.width = coveragePct + '%'; }
if (railRev) { railRev.style.width = (100 - coveragePct) + '%'; }

    const risksHtml=[];
    riskAlerts.forEach(alert=>risksHtml.push(riskCard({
      title:alert.title||'Actionable alert requires review',
      badge:String(alert.level||'Risk'),
      impact:alert.reason||'An operator alert requires review before stakeholder output is shared.',
      action:alert.recommended_action||'Review the alert context and confirm whether operational action is required.',
      location:alert.source?`Source: ${alert.source}`:'System - Runtime Status',
      href:'/operator/observability'
    })));
    if(rc.discovered>0)risksHtml.push(riskCard({title:'Discovery backlog awaiting review',badge:'Review',impact:`${rc.discovered} site(s) are known but not yet governed.`,action:'Review discovered sites and decide whether to monitor, reject, or keep pending.',location:'Estate - Discovered Sites',href:'/estate#discovered-sites'}));
    if(!risksHtml.length)risksHtml.push(riskCard({title:'No immediate operational risks detected',badge:'OK',impact:'No actionable alert or discovery backlog requires immediate review.',action:'Continue monitoring estate health and source freshness.',location:'Command Centre',href:'/'}));
    setHtml('jom-final-risk-list',risksHtml.join(''));
    const actions=[];
    riskAlerts.slice(0,1).forEach(alert=>actions.push(actionItem(alert.title||'Review actionable alert',alert.recommended_action||'Confirm alert impact before stakeholder output is shared.','/operator/observability')));
    if(rc.discovered>0)actions.push(actionItem('Open Discovered Sites',`${rc.discovered} discovered site(s) need an Estate review decision.`,'/estate#discovered-sites'));
    actions.push(actionItem('Inspect monitored estate','Use Estate to select a site and open Site Workspace when investigation is needed.','/estate'));
    setHtml('jom-final-action-list',actions.slice(0,3).join(''));
    setHtml('jom-final-status-list',[tile('Runtime',runtimeOk?'ok':'review','Live reporting/runtime route responding.',runtimeOk?'ok':'warn'),tile('Registry',`${rc.monitored} monitored`,`${rc.discovered} awaiting review`,rc.discovered?'warn':'ok'),tile('Alerts',`${actionableAlertCount} actionable`,'warning/critical operator alert feed',actionableAlertCount?'risk':'ok'),tile('Users',`${usersAnalysed||'n/a'}`,'users analysed by footprint source','ok')].join(''));
    setText('jom-final-discovery-summary',`${rc.discovered} site(s) require review before monitoring decisions are complete.`)
  }
  document.addEventListener('DOMContentLoaded',()=>{init().catch(err=>{console.error('Command Centre completion failed',err);setHtml('jom-final-risk-list',riskCard({title:'Command Centre data unavailable',badge:'Review',impact:'The browser could not load one or more live operator contracts.',action:'Check JOM runtime and source health before using Command Centre output.',location:'System - Runtime Status',href:'/health'}));setHtml('jom-final-action-list',actionItem('Check runtime status','Confirm the application and operator endpoints are responding.','/health'))})})
})();


/* --- JOM COMMAND CENTRE RAIL TRUTH DISPLAY FIX v1 START ---
   Data-only connection fix.
   No layout, HTML, CSS, card, navigation, or section changes.
*/
(function () {
  function unwrapContract(payload) {
    if (payload && typeof payload === "object" && payload.data && typeof payload.data === "object") {
      return payload.data;
    }
    return payload || {};
  }

  function safeNumber(value, fallback) {
    const n = Number(value);
    return Number.isFinite(n) ? n : fallback;
  }

  function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value == null || value === "" ? "n/a" : String(value);
  }

  function getRegistrySummary(registryPayload) {
    const registry = unwrapContract(registryPayload);
    const sites = Array.isArray(registry.sites) ? registry.sites : [];
    const summary = registry.summary || {};
    const total = safeNumber(summary.total_sites, sites.length);
    const monitored = safeNumber(summary.monitored_count, sites.filter(s => s && (s.is_monitored || s.classification === "monitored")).length);
    const discovered = safeNumber(summary.discovered_count, sites.filter(s => s && s.classification === "discovered").length);
    const pending = safeNumber(summary.pending_onboarding_count, sites.filter(s => s && String(s.collector_onboarding_status || "").includes("pending")).length);
    return { total, monitored, discovered, pending, sites };
  }

  function getUserDisplay(userPayload) {
    const payload = unwrapContract(userPayload);
    const summary = payload.summary || {};
    const users =
      safeNumber(summary.users_analyzed, null) ??
      safeNumber(summary.named_unique_users, null) ??
      safeNumber(summary.total_users, null) ??
      safeNumber(payload.users_analyzed, null);

    if (users !== null && users !== undefined) return users;

    const sourceStatus = String(payload.source_status || payload.status || "").toLowerCase();
    const safeToShow = payload.safe_to_show_named_access_ui;
    if (safeToShow === false || sourceStatus === "unavailable") return "Guarded";

    return "n/a";
  }

  function getDataHealth(sourceStatePayload, summaryPayload) {
    const sourceState = unwrapContract(sourceStatePayload);
    const summary = unwrapContract(summaryPayload);

    const reliability =
      sourceState.source_reliability ||
      sourceState.reliability ||
      (sourceState.sources && sourceState.sources.reliability) ||
      {};

    const freshness =
      sourceState.source_freshness ||
      sourceState.freshness ||
      (sourceState.sources && sourceState.sources.freshness) ||
      {};

    const liveProduct =
      sourceState.live_product_access ||
      sourceState.runtime_live_truth_status ||
      {};

    const posture = String(summary.posture || sourceState.posture || "").toLowerCase();
    const reliabilityStatus = String(reliability.overall_status || reliability.status || "").toLowerCase();
    const freshnessState = String(
      freshness.overall_state ||
      (freshness.data && freshness.data.summary && freshness.data.summary.overall_state) ||
      freshness.status ||
      ""
    ).toLowerCase();

    if (posture === "critical" || reliabilityStatus === "critical" || freshnessState === "critical") return "Critical";
    if (posture === "warning" || reliabilityStatus === "attention" || freshnessState === "attention" || freshnessState === "stale") return "Review";
    if (String(liveProduct.status || "").toLowerCase() === "partial") return "Review";
    if (posture === "ok" || reliabilityStatus === "ok" || freshnessState === "ok" || freshnessState === "current") return "OK";

    return "Check";
  }

  async function getJson(url) {
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) throw new Error(url + " returned " + res.status);
    return await res.json();
  }

  async function refreshCommandCentreRailTruth() {
    try {
      const [summary, alerts, registry, users, sourceState] = await Promise.all([
        getJson("/operator/summary").catch(() => ({})),
        getJson("/operator/alerts").catch(() => ({})),
        getJson("/registry/sites").catch(() => ({})),
        getJson("/users/footprint").catch(() => ({})),
        getJson("/api/source-state").catch(() => ({}))
      ]);

      const reg = getRegistrySummary(registry);
      const alertCount = safeNumber(alerts.count, Array.isArray(alerts.alerts) ? alerts.alerts.length : 0);

      setText("jom-rail-total-sites", reg.total);
      setText("jom-rail-monitored-sites", reg.monitored);
      setText("jom-rail-review-items", reg.discovered + reg.pending);
      setText("jom-rail-data-health", getDataHealth(sourceState, summary));

      setText("jom-rail-runtime", summary.runtime && summary.runtime.state ? summary.runtime.state : "OK");
      setText("jom-rail-alerts", alertCount);
      setText("jom-rail-users", getUserDisplay(users));

      setText("jom-rail-coverage-monitored", reg.monitored);
      setText("jom-rail-coverage-review", reg.discovered + reg.pending);

      const coverage = reg.total > 0 ? Math.round((reg.monitored / reg.total) * 100) : 0;
      setText("jom-rail-monitoring-coverage", coverage + "%");

      const reason = document.getElementById("jom-rail-coverage-reason");
      if (reason) {
        reason.textContent = reg.monitored + " monitored - " + (reg.discovered + reg.pending) + " awaiting review";
      }
    } catch (err) {
      console.warn("Command Centre rail truth display refresh failed", err);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", refreshCommandCentreRailTruth);
  } else {
    refreshCommandCentreRailTruth();
  }
})();
/* --- JOM COMMAND CENTRE RAIL TRUTH DISPLAY FIX v1 END --- */


/* --- JOM COMMAND CENTRE STATUS INTERPRETATION FIX v1 START ---
   Data interpretation only.
   No layout, HTML, CSS, navigation, card, rail, or section changes.
*/
(function () {
  function unwrap(payload) {
    if (payload && typeof payload === "object" && payload.data && typeof payload.data === "object") {
      return payload.data;
    }
    return payload || {};
  }

  function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value == null || value === "" ? "n/a" : String(value);
  }

  async function getJson(url) {
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) throw new Error(url + " returned " + res.status);
    return await res.json();
  }

  function deriveDataHealth(sourceStatePayload) {
    const sourceState = unwrap(sourceStatePayload);

    const freshnessContract = sourceState.source_freshness || {};
    const freshnessData = unwrap(freshnessContract);
    const freshnessSummary = freshnessData.summary || {};

    const reliabilityContract = sourceState.source_reliability || {};
    const reliabilityData = unwrap(reliabilityContract);
    const reliabilitySummary = reliabilityData.summary || {};

    const freshnessOverall = String(
      freshnessSummary.overall_state ||
      freshnessData.overall_state ||
      freshnessContract.status ||
      ""
    ).toLowerCase();

    const reliabilityOverall = String(
      reliabilityData.overall_status ||
      reliabilityContract.status ||
      ""
    ).toLowerCase();

    const issueCount = Number(
      reliabilitySummary.issue_count ??
      reliabilityData.summary?.issue_count ??
      0
    );

    if (freshnessOverall === "critical" || reliabilityOverall === "critical") return "Critical";
    if (
      freshnessOverall === "attention" ||
      freshnessOverall === "stale" ||
      reliabilityOverall === "attention" ||
      issueCount > 0
    ) {
      return "Review";
    }

    if (
      freshnessOverall === "ok" ||
      freshnessOverall === "current" ||
      reliabilityOverall === "ok"
    ) {
      return "OK";
    }

    return "Review";
  }

  function deriveUsers(userPayload) {
    const payload = unwrap(userPayload);
    const summary = payload.summary || {};

    const userCount = Number(
      summary.users_analyzed ??
      summary.named_unique_users ??
      summary.total_users ??
      payload.users_analyzed
    );

    if (Number.isFinite(userCount)) return userCount;

    const sourceStatus = String(payload.source_status || payload.status || "").toLowerCase();

    if (payload.safe_to_show_named_access_ui === false || sourceStatus === "unavailable") {
      return "Guarded";
    }

    return "n/a";
  }

  async function refreshCommandCentreStatusInterpretation() {
    try {
      const [sourceState, users] = await Promise.all([
        getJson("/api/source-state").catch(() => ({})),
        getJson("/users/footprint").catch(() => ({}))
      ]);

      setText("jom-rail-data-health", deriveDataHealth(sourceState));
      setText("jom-rail-users", deriveUsers(users));
    } catch (err) {
      console.warn("Command Centre status interpretation refresh failed", err);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", refreshCommandCentreStatusInterpretation);
  } else {
    refreshCommandCentreStatusInterpretation();
  }
})();
/* --- JOM COMMAND CENTRE STATUS INTERPRETATION FIX v1 END --- */


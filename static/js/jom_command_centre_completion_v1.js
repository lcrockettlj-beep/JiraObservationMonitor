
(function(){
  'use strict';
  const endpoint = '/api/workspace/command-centre';

  function unwrap(x){
    if(x && typeof x === 'object' && x.data && typeof x.data === 'object') return x.data;
    return x || {};
  }
  function n(v){ const x = Number(v); return Number.isFinite(x) ? x : null; }
  function firstNumber(...vals){ for(const v of vals){ const x=n(v); if(x!==null) return x; } return null; }
  function firstText(...vals){ for(const v of vals){ if(v !== undefined && v !== null && String(v).trim() !== '') return String(v); } return null; }

  function setCoverageReasonHidden(){
    const el = document.getElementById('jom-rail-coverage-reason');
    if(el){
      el.textContent = '';
      el.setAttribute('aria-hidden', 'true');
      el.style.display = 'none';
    }
  }
  function setText(id, value){ const el=document.getElementById(id); if(el) el.textContent = (value===null || value===undefined || value==='') ? 'n/a' : String(value); }
  function setHtml(id, html){ const el=document.getElementById(id); if(el) el.innerHTML = html; }
  function get(obj, path){
    let cur = obj;
    for(const part of path.split('.')){
      if(cur && typeof cur === 'object' && part in cur) cur = cur[part]; else return undefined;
    }
    return cur;
  }
  function arr(v){ return Array.isArray(v) ? v : []; }

  async function fetchWorkspace(){
    const res = await fetch(endpoint, {cache:'no-store'});
    if(!res.ok) throw new Error(endpoint + ' returned ' + res.status);
    return await res.json();
  }

  function deriveUsers(root){
    return firstNumber(
      get(root,'users.metric'), get(root,'users_metric.metric'), get(root,'metrics.users.metric'),
      get(root,'source_state.live_product_access.total_jira_product_user_count'),
      get(root,'live_product_access.total_jira_product_user_count'),
      get(root,'estate_product_access.summary.total_jira_product_user_count'),
      get(root,'product_access.summary.total_jira_product_user_count'),
      get(root,'admin_truth.live_product_access_truth.summary.total_jira_product_user_count')
    );
  }

  function deriveRegistry(root){
    const registry = unwrap(get(root,'registry') || get(root,'site_registry') || get(root,'registry_sites') || {});
    const summary = get(registry,'summary') || get(root,'registry_summary') || get(root,'coverage') || get(root,'metrics.coverage') || {};
    const sites = arr(registry.sites || root.sites);
    const total = firstNumber(summary.total_sites, summary.total, sites.length);
    const monitored = firstNumber(summary.monitored_count, summary.monitored, sites.filter(s => s && (s.is_monitored || s.classification === 'monitored')).length);
    const discovered = firstNumber(summary.discovered_count, summary.discovered, sites.filter(s => s && s.classification === 'discovered').length);
    const pending = firstNumber(summary.pending_onboarding_count, summary.pending, sites.filter(s => s && String(s.collector_onboarding_status || '').includes('pending')).length);
    return {total: total || 0, monitored: monitored || 0, discovered: discovered || 0, pending: pending || 0, review: (discovered || 0) + (pending || 0)};
  }

  function deriveDataHealth(root){
    const direct = firstText(get(root,'data_health'), get(root,'metrics.data_health'), get(root,'health.data_health'));
    if(direct) return direct;
    const ss = unwrap(get(root,'source_state') || {});
    const freshness = unwrap(ss.source_freshness || ss.freshness || {});
    const reliability = unwrap(ss.source_reliability || ss.reliability || {});
    const freshnessState = String(get(freshness,'summary.overall_state') || freshness.overall_state || freshness.status || '').toLowerCase();
    const relState = String(reliability.overall_status || reliability.status || '').toLowerCase();
    const issueCount = n(get(reliability,'summary.issue_count')) || 0;
    if(freshnessState === 'critical' || relState === 'critical') return 'Critical';
    if(['attention','stale','aging','review'].includes(freshnessState) || ['attention','review'].includes(relState) || issueCount > 0) return 'Review';
    if(['ok','current'].includes(freshnessState) || relState === 'ok') return 'OK';
    return 'Review';
  }

  function deriveRuntime(root){
    const state = firstText(get(root,'runtime.state'), get(root,'operator_summary.runtime.state'), get(root,'summary.runtime.state'));
    if(!state) return 'OK';
    return state === 'idle' ? 'OK' : state;
  }

  function deriveAlerts(root){
    const alerts = get(root,'operator_alerts.alerts') || get(root,'alerts.alerts') || get(root,'operator_summary.top_alerts') || get(root,'top_alerts') || [];
    const count = firstNumber(get(root,'operator_alerts.count'), get(root,'alerts.count'), get(root,'operator_summary.alert_summary.total'), get(root,'alert_summary.total'), arr(alerts).length);
    return {count: count || 0, alerts: arr(alerts)};
  }


    function renderActionList(alerts){
    const target = document.getElementById('jom-final-risk-list');
    if(!target) return;
    const all = arr(alerts);
    const actionable = all.filter(a => {
      const level = String(a && a.level || '').toLowerCase();
      return level === 'critical' || level === 'warning';
    });
    const selected = (actionable.length ? actionable : all).slice(0, 3);
    if(!selected.length){
      target.innerHTML = '<div class="jom-final-empty">No immediate actions found.</div>';
      return;
    }
    const severityRank = {critical: 0, warning: 1, info: 2, ok: 3};
    selected.sort((a,b) => (severityRank[String(a.level || 'info').toLowerCase()] ?? 9) - (severityRank[String(b.level || 'info').toLowerCase()] ?? 9));
    const html = selected.map(a => {
      const level = String(a.level || 'info').toLowerCase();
      const title = escapeHtml(a.title || 'Action required');
      const reason = escapeHtml(a.reason || 'Review operational source.');
      const action = escapeHtml(a.recommended_action || a.action || 'Open relevant operational view.');
      const source = a.source ? `<div><strong>FIX LOCATION</strong> Source: ${escapeHtml(a.source)}</div>` : '';
      return `<article class="jom-final-risk-card"><span class="jom-risk-pill">${level}</span><h3>${title}</h3><div><strong>IMPACT</strong> ${reason}</div><div><strong>ACTION</strong> ${action}</div>${source}<button class="jom-final-action">Open</button></article>`;
    }).join('');
    target.innerHTML = html;
  }

  function render(root){
    const registry = deriveRegistry(root);
    const users = deriveUsers(root);
    const alerts = deriveAlerts(root);
    const coverage = registry.total > 0 ? Math.round((registry.monitored / registry.total) * 100) : 0;
    setText('jom-rail-monitoring-coverage', coverage + '%');
    setText('jom-rail-coverage-monitored', registry.monitored);
    setText('jom-rail-coverage-review', registry.review);
    setCoverageReasonHidden();
    setText('jom-rail-total-sites', registry.total);
    setText('jom-rail-monitored-sites', registry.monitored);
    setText('jom-rail-review-items', registry.review);
    setText('jom-rail-data-health', deriveDataHealth(root));
    setText('jom-rail-runtime', deriveRuntime(root));
    setText('jom-rail-alerts', alerts.count);
    setText('jom-rail-users', users === null ? 'n/a' : users);
    renderActionList(alerts.alerts);
  }

  function boot(){
    fetchWorkspace().then(payload => render(unwrap(payload))).catch(err => {
      console.warn('Command Centre workspace contract render failed', err);
    });
  }
  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
// JOM Command Centre Action Required Stable Render v1 applied


/* --- JOM COMMAND CENTRE COVERAGE TEXT RENDER FIX v1 START ---
   Data rendering only.
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

  function asNumber(value, fallback) {
    const n = Number(value);
    return Number.isFinite(n) ? n : fallback;
  }

  async function getJson(url) {
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) throw new Error(url + " returned " + res.status);
    return await res.json();
  }

  function deriveRegistryMetrics(payload) {
    const root = unwrap(payload);
    const registry = unwrap(root.registry || root.site_registry || root);
    const summary = registry.summary || {};
    const sites = Array.isArray(registry.sites) ? registry.sites : [];

    const total = asNumber(summary.total_sites, sites.length);
    const monitored = asNumber(
      summary.monitored_count,
      sites.filter((site) => site && (site.is_monitored || site.classification === "monitored")).length
    );
    const discovered = asNumber(
      summary.discovered_count,
      sites.filter((site) => site && site.classification === "discovered").length
    );
    const pending = asNumber(summary.pending_onboarding_count, 0);
    const review = discovered + pending;
    const coverage = total > 0 ? Math.round((monitored / total) * 100) : 0;

    return { total, monitored, review, coverage };
  }

  function applyCoverage(metrics) {
    setText("jom-rail-monitoring-coverage", metrics.coverage + "%");
    setText("jom-rail-coverage-monitored", metrics.monitored);
    setText("jom-rail-coverage-review", metrics.review);
    setText("jom-rail-total-sites", metrics.total);
    setText("jom-rail-monitored-sites", metrics.monitored);
    setText("jom-rail-review-items", metrics.review);
    setCoverageReasonHidden();
  }

  async function refreshCoverageText() {
    try {
      const payload = await getJson("/api/workspace/command-centre");
      applyCoverage(deriveRegistryMetrics(payload));
    } catch (err) {
      console.warn("Command Centre coverage text render fix failed", err);
    }
  }

  function run() {
    refreshCoverageText();
    setTimeout(refreshCoverageText, 300);
    setTimeout(refreshCoverageText, 1000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else {
    run();
  }
})();
/* --- JOM COMMAND CENTRE COVERAGE TEXT RENDER FIX v1 END --- */


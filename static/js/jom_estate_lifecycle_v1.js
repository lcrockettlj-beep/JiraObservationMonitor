
// JOM Estate Workspace Contract Consolidation v1
// Data-binding only. No layout, HTML, CSS, navigation, card, table, or section changes.
(function () {
  "use strict";
  function byId(id) { return document.getElementById(id); }
  function setText(id, value) { const el = byId(id); if (el) el.textContent = (value === null || value === undefined || value === "") ? "n/a" : String(value); }
  function safeNumber(value, fallback) { const n = Number(value); return Number.isFinite(n) ? n : fallback; }
  function unwrap(payload) { if (payload && typeof payload === "object" && payload.data && typeof payload.data === "object") return payload.data; return payload || {}; }
  function getSites(contract) { const data = unwrap(contract.registry || contract.site_registry || contract); return Array.isArray(data.sites) ? data.sites : []; }
  function siteLabel(site) { return site.site_name || site.name || site.site_key || site.url || "Unknown site"; }
  function siteStatus(site) { return site.status || site.classification || site.collector_onboarding_status || "review"; }
  async function fetchContract() { const response = await fetch("/api/workspace/estate", { cache: "no-store" }); if (!response.ok) throw new Error("/api/workspace/estate returned " + response.status); return await response.json(); }
  function renderRail(contract) {
    const summary = contract.summary || {}; const registry = unwrap(contract.registry || {}); const sites = getSites(contract);
    const total = safeNumber(summary.total_sites, sites.length);
    const monitored = safeNumber(summary.monitored_count, sites.filter(s => s && (s.is_monitored || s.classification === "monitored")).length);
    const discovered = safeNumber(summary.discovered_count, sites.filter(s => s && s.classification === "discovered").length);
    const pending = safeNumber(summary.pending_onboarding_count, sites.filter(s => s && String(s.collector_onboarding_status || "").includes("pending")).length);
    const ignored = safeNumber(summary.ignored_count, sites.filter(s => s && s.classification === "ignored").length);
    setText("rail-total-sites", total); setText("rail-monitored-sites", monitored); setText("rail-discovered-sites", discovered);
    setText("rail-review-queue", discovered + pending); setText("rail-pending-sites", pending); setText("rail-ignored-sites", ignored);
    setText("rail-registry-status", contract.registry_status || registry.status || "active");
    const users = contract.users_summary || contract.user_summary || {}; const userCount = safeNumber(users.users_analyzed ?? users.total_jira_product_user_count ?? users.total_product_access_assignments, null);
    if (userCount !== null) setText("rail-users-count", userCount);
    const alertCount = safeNumber(contract.alert_count, Array.isArray(contract.alerts) ? contract.alerts.length : 0); setText("rail-alert-count", alertCount);
  }
  function renderRegistry(contract) {
    const body = byId("estate-registry-body"); if (!body) return; const sites = getSites(contract);
    if (!sites.length) { body.innerHTML = '<tr><td colspan="6">No estate sites available from the live estate workspace contract.</td></tr>'; return; }
    body.innerHTML = sites.map(site => { const status = siteStatus(site); const monitored = site.is_monitored || site.classification === "monitored" ? "Yes" : "No"; const approval = site.can_approve ? "Review" : "Current"; const productUsers = site.metrics && site.metrics.jira_product_user_count !== undefined ? site.metrics.jira_product_user_count : (site.jira_product_user_count ?? "n/a"); return '<tr><td>' + siteLabel(site) + '</td><td>' + (site.site_key || "n/a") + '</td><td>' + status + '</td><td>' + monitored + '</td><td>' + productUsers + '</td><td>' + approval + '</td></tr>'; }).join("");
  }
  function renderReviewQueue(contract) {
    const list = byId("estate-review-list"); const count = byId("estate-review-count"); if (!list && !count) return; const sites = getSites(contract);
    const candidates = sites.filter(site => site && (site.classification === "discovered" || site.can_approve || String(site.collector_onboarding_status || "").includes("pending")));
    if (count) count.textContent = String(candidates.length); if (!list) return;
    if (!candidates.length) { list.innerHTML = '<li>No sites currently awaiting Estate review.</li>'; return; }
    list.innerHTML = candidates.map(site => '<li><strong>' + siteLabel(site) + '</strong><span>' + siteStatus(site) + '</span></li>').join("");
  }
  function renderSources(contract) { const sourceState = contract.source_state || {}; const freshness = sourceState.source_freshness || {}; const reliability = sourceState.source_reliability || {}; const health = freshness.status || reliability.status || sourceState.status || "ok"; setText("estate-source-health", health); }
  async function loadEstateWorkspace() { try { const contract = await fetchContract(); renderRail(contract); renderRegistry(contract); renderReviewQueue(contract); renderSources(contract); } catch (error) { console.warn("Estate workspace contract load failed", error); setText("rail-registry-status", "review"); } }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", loadEstateWorkspace); else loadEstateWorkspace();
})();

// JOM Estate Data Render Runtime Repair v1
// Full single-owner Estate client script. No overlays. No backend, HTML, CSS, or route changes.
(function () {
  "use strict";

  let estateContract = {};
  let estateData = {};
  let estateSites = [];

  function byId(id) { return document.getElementById(id); }

  function setText(id, value) {
    const el = byId(id);
    if (!el) return;
    el.textContent = (value === null || value === undefined || value === "") ? "n/a" : String(value);
  }

  function safeNumber(value, fallback) {
    const n = Number(value);
    return Number.isFinite(n) ? n : fallback;
  }

  function escapeHtml(value) {
    return String(value === null || value === undefined ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function unwrap(payload) {
    if (payload && typeof payload === "object" && payload.data && typeof payload.data === "object") return payload.data;
    return payload && typeof payload === "object" ? payload : {};
  }

  function registryPayload(contract) {
    const data = unwrap(contract || estateContract);
    const registry = unwrap(data.registry || data.site_registry || {});
    if (Array.isArray(registry.sites)) return registry;
    if (Array.isArray(data.sites)) return data;
    return registry;
  }

  function getSites(contract) {
    const registry = registryPayload(contract || estateContract);
    return Array.isArray(registry.sites) ? registry.sites.filter(function (site) { return site && typeof site === "object"; }) : [];
  }

  function getSummary(contract) {
    const data = unwrap(contract || estateContract);
    const registry = registryPayload(contract || estateContract);
    return data.summary || data.registry_summary || registry.summary || {};
  }

  function siteKey(site) {
    return site.site_key || site.key || site.cloud_id || site.site_name || site.name || "site";
  }

  function siteLabel(site) {
    return site.site_name || site.name || site.site_key || site.key || site.site_url || site.url || "Unknown site";
  }

  function siteUrl(site) {
    return site.site_url || site.url || "";
  }

  function siteLifecycle(site) {
    if (!site || typeof site !== "object") return "review";
    return String(site.classification || site.lifecycle || site.collector_onboarding_status || site.status || "review");
  }

  function siteMonitoring(site) {
    return (site.is_monitored === true || site.monitored === true || String(site.classification || "").toLowerCase() === "monitored") ? "Monitored" : "Not monitored";
  }

  function siteHealth(site) {
    const value = String(site.health || site.health_status || site.source_status || site.status || "not available").toLowerCase();
    if (value === "ok" || value === "monitored") return "OK";
    if (value === "error" || value === "failed" || value === "review") return "Review";
    return value === "not available" ? "Not available" : value;
  }

  function siteOwner(site) {
    return "";
  }

  function siteLastObservation(site) {
    const registry = registryPayload(estateContract);
    const sourceState = estateData.source_state || {};
    const freshness = unwrap(sourceState.source_freshness || {});
    return site.last_observed_at ||
      site.last_observation_at ||
      site.last_seen_at ||
      site.updated_at_utc ||
      site.generated_at_utc ||
      site.generated_at ||
      registry.generated_at_utc ||
      estateData.generated_at_utc ||
      estateContract.generated_at_utc ||
      estateContract.served_at_utc ||
      freshness.generated_at_utc ||
      "Source timestamp unavailable";
  }

  function isPending(site) {
    const lifecycle = siteLifecycle(site).toLowerCase();
    const onboarding = String(site.collector_onboarding_status || "").toLowerCase();
    return lifecycle.includes("pending") || onboarding.includes("pending") || site.can_approve === true;
  }

  function siteMatchesFilter(site, filterValue) {
    const value = String(filterValue || "all").toLowerCase();
    const lifecycle = siteLifecycle(site).toLowerCase();
    if (value === "all") return true;
    if (value === "monitored") return site.is_monitored === true || site.monitored === true || lifecycle === "monitored";
    if (value === "discovered") return lifecycle === "discovered" && !(site.is_monitored === true || site.monitored === true);
    if (value === "pending") return isPending(site);
    if (value === "ignored") return lifecycle === "ignored";
    return true;
  }

  function siteMatchesSearch(site, query) {
    const q = String(query || "").trim().toLowerCase();
    if (!q) return true;
    const text = [
      site.site_name, site.name, site.site_key, site.key, site.cloud_id, site.url, site.site_url,
      site.classification, site.status, site.collector_onboarding_status,
      site.owner, site.business_owner, site.technical_owner, site.admin_owner, site.contact
    ].filter(Boolean).join(" ").toLowerCase();
    return text.includes(q);
  }

  function currentFilteredSites() {
    const search = byId("estate-search");
    const filter = byId("estate-filter");
    const query = search ? search.value : "";
    const filterValue = filter ? filter.value : "all";
    return estateSites.filter(function (site) {
      return siteMatchesFilter(site, filterValue) && siteMatchesSearch(site, query);
    });
  }



  function registryVisibleSites() {
    return estateSites.filter(function (site) {
      return siteMonitoring(site) === "Monitored";
    });
  }

  function currentFilteredRegistrySites() {
    const search = byId("estate-search");
    const filter = byId("estate-filter");
    const query = search ? search.value : "";
    return registryVisibleSites().filter(function (site) {
      return siteMatchesSearch(site, query);
    });
  }

  function siteCell(site) {
    const label = escapeHtml(siteLabel(site));
    const url = siteUrl(site);
    if (url) return '<a class="estate-site-link" href="' + escapeHtml(url) + '" target="_blank" rel="noopener noreferrer">' + label + '</a>';
    return label;
  }

  function actionCell(site) {
    const key = encodeURIComponent(siteKey(site));
    return '<a class="estate-site-link estate-site-link--button" href="/estate/review/' + key + '">Manage</a>';
  }

  async function fetchContract() {
    const response = await fetch("/api/workspace/estate", { cache: "no-store" });
    if (!response.ok) throw new Error("/api/workspace/estate returned " + response.status);
    return await response.json();
  }

  function renderRail(contract) {
    const summary = getSummary(contract);
    const sites = getSites(contract);
    const registry = registryPayload(contract);
    const total = safeNumber(summary.total_sites, sites.length);
    const monitored = safeNumber(summary.monitored_count, sites.filter(function (site) { return siteMonitoring(site) === "Monitored"; }).length);
    const discovered = safeNumber(summary.discovered_count, sites.filter(function (site) { return siteLifecycle(site).toLowerCase() === "discovered"; }).length);
    const pending = safeNumber(summary.pending_onboarding_count, sites.filter(isPending).length);
    const ignored = safeNumber(summary.ignored_count, sites.filter(function (site) { return siteLifecycle(site).toLowerCase() === "ignored"; }).length);

    setText("rail-total-sites", total);
    setText("rail-monitored-sites", monitored);
    setText("rail-discovered-sites", discovered);
    setText("rail-review-queue", discovered + pending);
    setText("rail-pending-sites", pending);
    setText("rail-ignored-sites", ignored);
    setText("rail-registry-status", estateData.registry_status || registry.status || "OK");

    const estateProduct = unwrap(estateData.estate_product_access || {});
    const productSummary = estateProduct.summary || estateProduct.product_summary || {};
    const users = estateData.users || estateData.user_summary || estateData.users_summary || {};
    const userCount = safeNumber(productSummary.total_jira_product_user_count ?? users.users_analyzed ?? users.total_jira_product_user_count ?? users.total_product_access_assignments, null);
    setText("rail-users-count", userCount === null ? "--" : userCount);

    const alerts = estateData.alerts || estateData.operator_alerts || {};
    const alertCount = safeNumber(estateData.alert_count, Array.isArray(alerts) ? alerts.length : safeNumber(alerts.count, 0));
    setText("rail-alert-count", alertCount);
  }

  function renderRegistryRows(sites) {
    const body = byId("estate-registry-body");
    if (!body) return;
    if (!sites.length) {
      body.innerHTML = '<tr><td colspan="6">No monitored sites match the current search.</td></tr>';
      return;
    }
    body.innerHTML = sites.map(function (site) {
      return '<tr>' +
        '<td>' + siteCell(site) + '</td>' +
        '<td>' + escapeHtml(siteLifecycle(site)) + '</td>' +
        '<td>' + escapeHtml(siteMonitoring(site)) + '</td>' +
        '<td>' + escapeHtml(siteHealth(site)) + '</td>' +
        '<td>' + escapeHtml(siteLastObservation(site)) + '</td>' +
        '<td>' + actionCell(site) + '</td>' +
      '</tr>';
    }).join("");
  }

  function renderRegistry(contract) {
    estateSites = getSites(contract);
    renderRegistryRows(currentFilteredRegistrySites());
  }

  function renderReviewQueue(contract) {
    const list = byId("estate-review-list");
    const count = byId("estate-review-count");
    const sites = getSites(contract);
    const candidates = sites.filter(function (site) {
      const lifecycle = siteLifecycle(site).toLowerCase();
      return lifecycle === "discovered" || isPending(site);
    });
    if (count) count.textContent = String(candidates.length);
    if (!list) return;
    if (!candidates.length) {
      list.innerHTML = '<p class="estate-empty">No sites currently awaiting Estate review.</p>';
      return;
    }
    list.innerHTML = candidates.map(function (site) {
      const key = encodeURIComponent(siteKey(site));
      return '<div class="estate-review-item"><strong>' + escapeHtml(siteLabel(site)) + '</strong><a class="estate-site-link estate-site-link--button" href="/estate/review/' + key + '">Review</a></div>';
    }).join("");
  }

  function renderSources(contract) {
    const sourceState = estateData.source_state || {};
    const freshness = unwrap(sourceState.source_freshness || {});
    const reliability = unwrap(sourceState.source_reliability || {});
    const health = freshness.status || reliability.status || sourceState.status || "ok";
    setText("estate-source-health", health);
  }

  function showRenderError(error) {
    const message = error && error.message ? error.message : String(error || "Unknown error");
    const body = byId("estate-registry-body");
    const list = byId("estate-review-list");
    if (body) body.innerHTML = '<tr><td colspan="6">Estate render error: ' + escapeHtml(message) + '</td></tr>';
    if (list) list.innerHTML = '<p class="estate-empty">Estate render error: ' + escapeHtml(message) + '</p>';
    setText("rail-registry-status", "review");
  }

  function applySearchAndFilter() {
    try { renderRegistryRows(currentFilteredRegistrySites()); }
    catch (error) { showRenderError(error); }
  }

  function bindSearchAndFilterControls() {
    const search = byId("estate-search");
    const filter = byId("estate-filter");
    if (search) search.addEventListener("input", applySearchAndFilter);
    if (filter) filter.addEventListener("change", applySearchAndFilter);
  }

  async function loadEstateWorkspace() {
    try {
      estateContract = await fetchContract();
      estateData = unwrap(estateContract);
      estateSites = getSites(estateContract);
      renderRail(estateContract);
      renderRegistry(estateContract);
      renderReviewQueue(estateContract);
      renderSources(estateContract);
    } catch (error) {
      console.warn("Estate workspace contract load failed", error);
      showRenderError(error);
    }
  }

  function init() {
    bindSearchAndFilterControls();
    loadEstateWorkspace();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();

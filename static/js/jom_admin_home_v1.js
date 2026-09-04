(() => {
  "use strict";
  const endpoints = {
    estate: "/api/admin/estate-configuration",
    monitoring: "/api/admin/monitoring",
    licensing: "/api/admin/licensing-billing",
    users: "/api/admin/users-access",
    system: "/api/admin/system-configuration"
  };
  const byId = (id) => document.getElementById(id);
  const text = (id, value) => { const node = byId(id); if (node) node.textContent = value; };
  const value = (input, suffix = "") => input === null || input === undefined || input === "" ? "Unavailable" : `${input}${suffix}`;
  const safeSummary = (payload) => payload && typeof payload.summary === "object" ? payload.summary : {};
  const normalStatus = (payload) => String(payload && payload.status || "unavailable").toLowerCase();
  const formatTime = (input) => {
    if (!input) return null;
    const date = new Date(input);
    return Number.isNaN(date.getTime()) ? null : date.toLocaleString();
  };
  async function read(name, url) {
    try {
      const response = await fetch(url, { headers: { Accept: "application/json" }, cache: "no-store" });
      let payload = null;
      try { payload = await response.json(); } catch (_) { payload = null; }
      if (!response.ok || !payload) throw new Error(`${name}: HTTP ${response.status}`);
      return { name, ok: true, payload };
    } catch (error) {
      return { name, ok: false, error: String(error && error.message || error) };
    }
  }
  function render(results) {
    const map = Object.fromEntries(results.map((result) => [result.name, result]));
    const estate = map.estate.ok ? map.estate.payload : {};
    const monitoring = map.monitoring.ok ? map.monitoring.payload : {};
    const licensing = map.licensing.ok ? map.licensing.payload : {};
    const users = map.users.ok ? map.users.payload : {};
    const system = map.system.ok ? map.system.payload : {};
    const es = safeSummary(estate), ms = safeSummary(monitoring), ls = licensing.estate || {}, us = safeSummary(users), ss = safeSummary(system);

    text("admin-estate-primary", `${value(es.monitored_sites)} monitored sites`);
    text("admin-estate-detail", `Ownership coverage ${value(es.ownership_coverage_percent, "%")}; ${value(es.failed_sources)} failed sources.`);
    text("admin-monitoring-primary", `${value(ms.monitoring_coverage_percent, "%")} coverage`);
    text("admin-monitoring-detail", `${value(ms.monitored_sites)} of ${value(ms.total_sites)} sites monitored; ${value(ms.failed_sources)} failed sources.`);
    text("admin-licensing-primary", `${value(ls.product_users)} product assignments`);
    text("admin-licensing-detail", `${value(ls.monitored_sites)} monitored sites. Commercial billing: ${licensing.billing_evidence ? licensing.billing_evidence.commercial_contract || "Unavailable" : "Unavailable"}.`);
    text("admin-users-primary", `${value(us.org_users)} organisation accounts`);
    text("admin-users-detail", `Managed coverage ${value(us.managed_coverage_percent, "%")}; MFA coverage ${value(us.mfa_coverage_percent, "%")}.`);
    text("admin-system-primary", String(ss.environment || "Unavailable"));
    text("admin-system-detail", `${value(ss.configured_sources)} configured sources; ${value(ss.failed_sources)} failed sources; ${value(ss.guardrails_enabled)} guardrails enabled.`);

    const failed = results.filter((result) => !result.ok);
    const review = results.filter((result) => result.ok && normalStatus(result.payload) !== "ok");
    const overall = failed.length ? "Unavailable" : review.length ? "Review" : "OK";
    text("admin-home-status", overall);
    text("admin-home-status-note", failed.length ? `${failed.length} Admin contract(s) could not be read.` : review.length ? `${review.length} Admin authority area(s) require review.` : "All connected Admin authority areas report OK.");
    const times = results.filter((r) => r.ok).map((r) => formatTime(r.payload.generated_at_utc)).filter(Boolean);
    text("admin-home-updated", times.length ? `Contracts served ${times.sort().slice(-1)[0]}` : "Contract time unavailable");
    const error = byId("admin-home-error");
    if (error && failed.length) {
      error.hidden = false;
      error.textContent = failed.map((item) => item.error).join(" | ");
    }
  }
  async function load() {
    const results = await Promise.all(Object.entries(endpoints).map(([name, url]) => read(name, url)));
    render(results);
  }
  document.addEventListener("DOMContentLoaded", load, { once: true });
})();

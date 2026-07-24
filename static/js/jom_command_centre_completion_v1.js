(function () {
  "use strict";
  const CONTRACT_URL = "/api/workspace/command-centre";

  function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value == null || value === "" ? "n/a" : String(value);
  }

  function safeNumber(value, fallback) {
    const n = Number(value);
    return Number.isFinite(n) ? n : fallback;
  }

  async function getContract() {
    const response = await fetch(CONTRACT_URL, { cache: "no-store" });
    if (!response.ok) throw new Error(CONTRACT_URL + " returned " + response.status);
    return await response.json();
  }

  function renderAlerts(contract) {
    const alerts = contract.alerts || {};
    const items = Array.isArray(alerts.items) ? alerts.items : [];
    const list = document.getElementById("jom-final-risk-list");
    if (!list) return;
    if (!items.length) {
      list.innerHTML = "<li>No immediate action required.</li>";
      return;
    }
    list.innerHTML = items.slice(0, 5).map(function (item) {
      const title = item.title || "Review item";
      const reason = item.reason || item.recommended_action || "Review backend source.";
      const level = item.level || "info";
      return "<li data-level=\"" + String(level).replace(/\"/g, "") + "\"><strong>" + title + "</strong><span>" + reason + "</span></li>";
    }).join("");
  }

  function render(contract) {
    const registry = contract.registry || {};
    const coverage = contract.coverage || {};
    const runtime = contract.runtime || {};
    const alerts = contract.alerts || {};
    const users = contract.users || {};
    const dataHealth = contract.data_health || {};
    const total = safeNumber(registry.total_sites, 0);
    const monitored = safeNumber(registry.monitored_count, 0);
    const review = safeNumber(registry.review_count, 0);
    const coveragePercent = safeNumber(coverage.coverage_percent, total > 0 ? Math.round((monitored / total) * 100) : 0);

    setText("jom-rail-total-sites", total);
    setText("jom-rail-monitored-sites", monitored);
    setText("jom-rail-review-items", review);
    setText("jom-rail-data-health", dataHealth.label || "Review");
    setText("jom-rail-runtime", runtime.state || "OK");
    setText("jom-rail-alerts", safeNumber(alerts.count, 0));
    setText("jom-rail-users", users.metric == null ? "n/a" : users.metric);
    setText("jom-rail-monitoring-coverage", coveragePercent + "%");
    setText("jom-rail-coverage-monitored", monitored);
    setText("jom-rail-coverage-review", review);
    setText("jom-rail-coverage-reason", coverage.reason || (monitored + " monitored - " + review + " awaiting review"));
    renderAlerts(contract);
  }

  async function boot() {
    try {
      render(await getContract());
    } catch (err) {
      console.warn("Command Centre workspace contract failed", err);
      setText("jom-rail-data-health", "Review");
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();

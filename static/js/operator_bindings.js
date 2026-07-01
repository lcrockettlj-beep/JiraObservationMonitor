(function (window, document) {
  "use strict";

  function text(selector, value) {
    const target = document.querySelector(selector);
    if (target) {
      target.textContent = value === undefined || value === null ? "" : String(value);
    }
  }

  function json(selector, value) {
    const target = document.querySelector(selector);
    if (target) {
      target.textContent = JSON.stringify(value, null, 2);
    }
  }

  function setStatusClass(selector, posture) {
    const target = document.querySelector(selector);
    if (!target) { return; }
    target.dataset.operatorPosture = posture || "unknown";
  }

  function alertText(alerts) {
    if (!Array.isArray(alerts) || alerts.length === 0) {
      return "No active operator alerts";
    }
    return alerts.map(function (item) {
      return [item.level, item.category, item.title].filter(Boolean).join(" | ");
    }).join("\n");
  }

  async function bindOperatorSummary() {
    if (!window.JOMOperatorAPI) { return null; }
    const summary = await window.JOMOperatorAPI.getOperatorSummary();

    text("[data-jom-bind='operator-posture']", summary.posture);
    text("[data-jom-bind='operator-alert-total']", summary.alert_summary && summary.alert_summary.total);
    text("[data-jom-bind='operator-alert-critical']", summary.alert_summary && summary.alert_summary.critical);
    text("[data-jom-bind='operator-alert-warning']", summary.alert_summary && summary.alert_summary.warning);
    text("[data-jom-bind='operator-alert-info']", summary.alert_summary && summary.alert_summary.info);
    text("[data-jom-bind='runtime-state']", summary.runtime && summary.runtime.state);
    text("[data-jom-bind='runtime-last-action']", summary.runtime && summary.runtime.last_action);
    text("[data-jom-bind='runtime-last-result']", summary.runtime && summary.runtime.last_result_status);
    json("[data-jom-bind='operator-summary-json']", summary);
    setStatusClass("[data-jom-bind='operator-posture']", summary.posture);

    return summary;
  }

  async function bindOperatorAlerts() {
    if (!window.JOMOperatorAPI) { return null; }
    const payload = await window.JOMOperatorAPI.getOperatorAlerts();
    const alerts = payload.alerts || [];

    text("[data-jom-bind='operator-alert-list']", alertText(alerts));
    json("[data-jom-bind='operator-alerts-json']", payload);

    return payload;
  }

  async function bindOperatorSurface() {
    if (!window.JOMOperatorAPI) { return null; }
    const surface = await window.JOMOperatorAPI.getOperatorSurface();

    text("[data-jom-bind='operator-surface-posture']", surface.posture);
    json("[data-jom-bind='operator-surface-json']", surface);

    return surface;
  }

  async function bindRuntimeStatus() {
    if (!window.JOMOperatorAPI) { return null; }
    const status = await window.JOMOperatorAPI.getRuntimeStatus();

    text("[data-jom-bind='runtime-status-state']", status.state);
    text("[data-jom-bind='runtime-status-running']", status.running);
    json("[data-jom-bind='runtime-status-json']", status);

    return status;
  }

  async function bindAll() {
    const results = {};
    try { results.summary = await bindOperatorSummary(); } catch (error) { results.summaryError = error; }
    try { results.alerts = await bindOperatorAlerts(); } catch (error) { results.alertsError = error; }
    try { results.surface = await bindOperatorSurface(); } catch (error) { results.surfaceError = error; }
    try { results.runtime = await bindRuntimeStatus(); } catch (error) { results.runtimeError = error; }
    return results;
  }

  window.JOMOperatorBindings = {
    bindAll: bindAll,
    bindOperatorSummary: bindOperatorSummary,
    bindOperatorAlerts: bindOperatorAlerts,
    bindOperatorSurface: bindOperatorSurface,
    bindRuntimeStatus: bindRuntimeStatus
  };

  document.addEventListener("DOMContentLoaded", function () {
    if (document.querySelector("[data-jom-bind]")) {
      bindAll();
    }
  });
})(window, document);

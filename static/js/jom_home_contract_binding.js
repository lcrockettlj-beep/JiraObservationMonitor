/*
 * JOM Home Contract Binding v1
 * Purpose: first low-risk page binding to the frozen frontend contract client.
 * Scope: Home page only.
 * Data sources: /operator/summary, /operator/alerts, /operator/observability via window.JOMClient.
 * Safety: no /api primary fetches, no CSS changes, no visual rebuild.
 */
(function () {
  'use strict';

  function isHomePage() {
    var path = (window.location && window.location.pathname) || '/';
    return path === '/' || path === '/home';
  }

  function setText(selector, value) {
    var node = document.querySelector(selector);
    if (node) { node.textContent = value == null ? '' : String(value); }
  }

  function setJson(selector, value) {
    var node = document.querySelector(selector);
    if (node) { node.textContent = JSON.stringify(value || {}, null, 2); }
  }

  function updateOptionalTargets(payload) {
    // This binding only updates explicit opt-in targets if they already exist.
    // It does not create new visual UI.
    var summary = payload.summary || {};
    var alerts = payload.alerts || {};
    var observability = payload.observability || {};
    setText('[data-jom-client="home-runtime-status"]', summary.runtime && summary.runtime.status);
    setText('[data-jom-client="home-source-health"]', summary.source_health && summary.source_health.status);
    setText('[data-jom-client="home-alert-count"]', alerts.count);
    setJson('[data-jom-client="home-observability-json"]', observability);
  }

  function publishState(state, detail) {
    window.JOMHomeContractState = Object.freeze({ state: state, detail: detail || {}, generatedAt: new Date().toISOString() });
    try {
      window.dispatchEvent(new CustomEvent('jom:home-contract-state', { detail: window.JOMHomeContractState }));
    } catch (error) {
      // Older browser fallback: state remains available on window.JOMHomeContractState.
    }
  }

  function loadHomeContracts() {
    if (!window.JOMClient) {
      publishState('unavailable', { reason: 'window.JOMClient is not available' });
      return Promise.resolve(null);
    }
    publishState('loading', {});
    return Promise.all([
      window.JOMClient.getOperatorSummary(),
      window.JOMClient.getOperatorAlerts(),
      window.JOMClient.getOperatorObservability()
    ]).then(function (results) {
      var payload = { summary: results[0], alerts: results[1], observability: results[2] };
      updateOptionalTargets(payload);
      publishState('ready', payload);
      return payload;
    }).catch(function (error) {
      publishState('error', { message: error && error.message ? error.message : 'Home contract data unavailable' });
      return null;
    });
  }

  function init() {
    if (!isHomePage()) { return; }
    loadHomeContracts();
  }

  window.JOMHomeContractBinding = Object.freeze({ init: init, loadHomeContracts: loadHomeContracts });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

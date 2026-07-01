/*
 * JOM Reference Contract Binding v1
 * Scope: Reference page read-only registry contract.
 * Primary source: /registry/sites via window.JOMClient.
 * Compatibility: /api/site-registry action flow remains retained separately.
 * Safety: no /api/data or /api/source-state primary fetches, no CSS changes, no visual rebuild.
 */
(function () {
  'use strict';
  function isReferencePage() { var path = (window.location && window.location.pathname) || ''; return path === '/reference'; }
  function setText(selector, value) { var node = document.querySelector(selector); if (node) { node.textContent = value == null ? '' : String(value); } }
  function setJson(selector, value) { var node = document.querySelector(selector); if (node) { node.textContent = JSON.stringify(value || {}, null, 2); } }
  function updateOptionalTargets(payload) {
    var registry = payload.registry || {};
    var summary = registry.summary || {};
    setText('[data-jom-client="reference-site-count"]', Array.isArray(registry.sites) ? registry.sites.length : 0);
    setText('[data-jom-client="reference-monitored-count"]', summary.monitored_count);
    setText('[data-jom-client="reference-discovered-count"]', summary.discovered_count);
    setJson('[data-jom-client="reference-registry-json"]', registry);
  }
  function publishState(state, detail) {
    window.JOMReferenceContractState = Object.freeze({ state: state, detail: detail || {}, generatedAt: new Date().toISOString() });
    try { window.dispatchEvent(new CustomEvent('jom:reference-contract-state', { detail: window.JOMReferenceContractState })); } catch (error) {}
  }
  function loadReferenceContracts() {
    if (!window.JOMClient) { publishState('unavailable', { reason: 'window.JOMClient is not available' }); return Promise.resolve(null); }
    publishState('loading', {});
    return window.JOMClient.getRegistrySites().then(function (registry) {
      var payload = { registry: registry };
      updateOptionalTargets(payload);
      publishState('ready', payload);
      return payload;
    }).catch(function (error) {
      publishState('error', { message: error && error.message ? error.message : 'Reference contract data unavailable' });
      return null;
    });
  }
  function init() { if (!isReferencePage()) { return; } loadReferenceContracts(); }
  window.JOMReferenceContractBinding = Object.freeze({ init: init, loadReferenceContracts: loadReferenceContracts });
  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', init); } else { init(); }
})();

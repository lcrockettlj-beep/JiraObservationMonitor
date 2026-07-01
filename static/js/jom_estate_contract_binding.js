/*
 * JOM Estate Contract Binding v1
 * Purpose: Estate page binding to the frozen frontend contract client.
 * Scope: Estate page only.
 * Data sources: /operator/surface, /registry/sites, /estate/product-access via window.JOMClient.
 * Safety: no /api primary fetches, no CSS changes, no visual rebuild.
 */
(function () {
  'use strict';

  function isEstatePage() {
    var path = (window.location && window.location.pathname) || '';
    return path === '/estate' || path.indexOf('/estate') === 0;
  }

  function setText(selector, value) {
    var node = document.querySelector(selector);
    if (node) { node.textContent = value == null ? '' : String(value); }
  }

  function setJson(selector, value) {
    var node = document.querySelector(selector);
    if (node) { node.textContent = JSON.stringify(value || {}, null, 2); }
  }

  function countArray(value) {
    return Array.isArray(value) ? value.length : 0;
  }

  function updateOptionalTargets(payload) {
    // This binding only updates explicit opt-in targets if they already exist.
    // It does not create new visual UI.
    var surface = payload.surface || {};
    var registry = payload.registry || {};
    var productAccess = payload.productAccess || {};
    var sites = Array.isArray(registry.sites) ? registry.sites : [];
    var accessSites = Array.isArray(productAccess.sites) ? productAccess.sites : [];

    setText('[data-jom-client="estate-site-count"]', countArray(sites));
    setText('[data-jom-client="estate-product-access-site-count"]', countArray(accessSites));
    setText('[data-jom-client="estate-runtime-status"]', surface.runtime && surface.runtime.status);
    setText('[data-jom-client="estate-alert-count"]', surface.alert_summary && surface.alert_summary.count);
    setJson('[data-jom-client="estate-surface-json"]', surface);
    setJson('[data-jom-client="estate-registry-json"]', registry);
    setJson('[data-jom-client="estate-product-access-json"]', productAccess);
  }

  function publishState(state, detail) {
    window.JOMEstateContractState = Object.freeze({ state: state, detail: detail || {}, generatedAt: new Date().toISOString() });
    try {
      window.dispatchEvent(new CustomEvent('jom:estate-contract-state', { detail: window.JOMEstateContractState }));
    } catch (error) {
      // Older browser fallback: state remains available on window.JOMEstateContractState.
    }
  }

  function loadEstateContracts() {
    if (!window.JOMClient) {
      publishState('unavailable', { reason: 'window.JOMClient is not available' });
      return Promise.resolve(null);
    }
    publishState('loading', {});
    return Promise.all([
      window.JOMClient.getOperatorSurface(),
      window.JOMClient.getRegistrySites(),
      window.JOMClient.getEstateProductAccess()
    ]).then(function (results) {
      var payload = { surface: results[0], registry: results[1], productAccess: results[2] };
      updateOptionalTargets(payload);
      publishState('ready', payload);
      return payload;
    }).catch(function (error) {
      publishState('error', { message: error && error.message ? error.message : 'Estate contract data unavailable' });
      return null;
    });
  }

  function init() {
    if (!isEstatePage()) { return; }
    loadEstateContracts();
  }

  window.JOMEstateContractBinding = Object.freeze({ init: init, loadEstateContracts: loadEstateContracts });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

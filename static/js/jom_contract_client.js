/*
 * JOM Frontend Contract Client Scaffold v1
 * Purpose: shared client for frozen operator contracts before frontend visual rebuild.
 * Rules:
 * - New frontend modules must not use /api/data or /api/source-state as primary sources.
 * - /api compatibility routes remain fallback-only until rebuild validation passes.
 * - This file does not bind to templates or change UI by itself.
 */
(function () {
  'use strict';
  var EXPECTED_KEYS = {
    '/operator/summary': ['schema', 'generated_at_utc', 'runtime', 'source_health', 'alert_summary', 'posture', 'observability'],
    '/operator/surface': ['schema', 'generated_at_utc', 'runtime', 'observability', 'alerts', 'sources', 'estate', 'admin'],
    '/operator/alerts': ['alerts', 'count'],
    '/operator/observability': ['runtime_status', 'runtime_history'],
    '/registry/sites': ['schema', 'generated_at_utc', 'policy', 'sites', 'summary'],
    '/estate/product-access': ['schema', 'generated_at_utc', 'scope', 'source', 'sites', 'summary'],
    '/admin/truth': ['schema', 'generated_at_utc', 'admin_identity', 'billing_truth', 'product_access_truth'],
    '/users/footprint': ['schema', 'generated_at_utc', 'summary', 'users', 'safe_to_show_named_access_ui']
  };
  var PRIMARY_API_BLOCKLIST = ['/api/data', '/api/source-state'];
  function requestJson(endpoint, options) {
    auditPrimaryEndpoint(endpoint, options || {});
    var requestOptions = Object.assign({ cache: 'no-store', credentials: 'same-origin' }, options || {});
    return fetch(endpoint, requestOptions).then(function (response) {
      if (!response.ok) {
        var error = new Error('Endpoint unavailable: ' + endpoint + ' HTTP ' + response.status);
        error.status = response.status; error.endpoint = endpoint; throw error;
      }
      return response.json().catch(function () {
        var error = new Error('Invalid JSON from endpoint: ' + endpoint);
        error.endpoint = endpoint; throw error;
      });
    });
  }
  function assertKeys(endpoint, payload, keys) {
    var required = keys || EXPECTED_KEYS[endpoint] || [];
    var missing = [];
    required.forEach(function (key) {
      if (!payload || !Object.prototype.hasOwnProperty.call(payload, key)) { missing.push(key); }
    });
    if (missing.length) {
      var error = new Error('Contract mismatch for ' + endpoint + ': missing ' + missing.join(', '));
      error.endpoint = endpoint; error.missingKeys = missing; throw error;
    }
    return payload;
  }
  function requestContract(endpoint, keys, options) {
    return requestJson(endpoint, options).then(function (payload) { return assertKeys(endpoint, payload, keys); });
  }
  function renderLoading(target, label) {
    var node = resolveTarget(target);
    if (node) { node.innerHTML = '<div class="jom-loading" data-jom-state="loading">' + escapeHtml(label || 'Loading...') + '</div>'; }
  }
  function renderError(target, message) {
    var node = resolveTarget(target);
    if (node) { node.innerHTML = '<div class="jom-error" data-jom-state="error">' + escapeHtml(message || 'Data unavailable.') + '</div>'; }
  }
  function withFallbackLabel(payload, endpoint) {
    var value = payload || {};
    if (value && typeof value === 'object') { value.__jom_fallback = true; value.__jom_fallback_endpoint = endpoint || 'unknown'; }
    return value;
  }
  function auditPrimaryEndpoint(endpoint, options) {
    var mode = options && options.jomUsage;
    if (PRIMARY_API_BLOCKLIST.indexOf(endpoint) !== -1 && mode !== 'fallback') { throw new Error('Blocked primary legacy API usage: ' + endpoint); }
    return true;
  }
  function resolveTarget(target) { if (!target) { return null; } if (typeof target === 'string') { return document.querySelector(target); } return target; }
  function escapeHtml(value) {
    return String(value || '').replace(/[&<>\"']/g, function (ch) {
      return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '\"': '&quot;', "'": '&#39;' })[ch];
    });
  }
  var client = {
    expectedKeys: EXPECTED_KEYS,
    requestJson: requestJson,
    requestContract: requestContract,
    assertKeys: assertKeys,
    renderLoading: renderLoading,
    renderError: renderError,
    withFallbackLabel: withFallbackLabel,
    auditPrimaryEndpoint: auditPrimaryEndpoint,
    getOperatorSummary: function () { return requestContract('/operator/summary'); },
    getOperatorSurface: function () { return requestContract('/operator/surface'); },
    getOperatorAlerts: function () { return requestContract('/operator/alerts'); },
    getOperatorObservability: function () { return requestContract('/operator/observability'); },
    getRegistrySites: function () { return requestContract('/registry/sites'); },
    getEstateProductAccess: function () { return requestContract('/estate/product-access'); },
    getAdminTruth: function () { return requestContract('/admin/truth'); },
    getUsersFootprint: function () { return requestContract('/users/footprint'); },
    legacyApiDataFallback: function () { return requestJson('/api/data', { jomUsage: 'fallback' }).then(function (payload) { return withFallbackLabel(payload, '/api/data'); }); },
    legacySourceStateFallback: function () { return requestJson('/api/source-state', { jomUsage: 'fallback' }).then(function (payload) { return withFallbackLabel(payload, '/api/source-state'); }); },
    legacySiteRegistryCompatibility: function () { return requestJson('/api/site-registry', { jomUsage: 'fallback' }).then(function (payload) { return withFallbackLabel(payload, '/api/site-registry'); }); }
  };
  window.JOMClient = Object.freeze(client);
})();

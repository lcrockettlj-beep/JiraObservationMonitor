/*
 * JOM Admin Contract Binding v1
 * Scope: Admin/reference admin data contract only.
 * Data sources: /admin/truth and /users/footprint via window.JOMClient.
 * Safety: no /api primary fetches, no CSS changes, no visual rebuild.
 */
(function () {
  'use strict';
  function isAdminSurface() {
    var path = (window.location && window.location.pathname) || '';
    return path === '/admin' || path.indexOf('/admin') === 0 || path === '/reference';
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
    var truth = payload.adminTruth || {};
    var footprint = payload.usersFootprint || {};
    setText('[data-jom-client="admin-generated-at"]', truth.generated_at_utc);
    setText('[data-jom-client="admin-user-count"]', footprint.summary && footprint.summary.user_count);
    setText('[data-jom-client="admin-safe-named-access"]', footprint.safe_to_show_named_access_ui);
    setJson('[data-jom-client="admin-truth-json"]', truth);
    setJson('[data-jom-client="admin-footprint-json"]', footprint);
  }
  function publishState(state, detail) {
    window.JOMAdminContractState = Object.freeze({ state: state, detail: detail || {}, generatedAt: new Date().toISOString() });
    try { window.dispatchEvent(new CustomEvent('jom:admin-contract-state', { detail: window.JOMAdminContractState })); } catch (error) {}
  }
  function loadAdminContracts() {
    if (!window.JOMClient) { publishState('unavailable', { reason: 'window.JOMClient is not available' }); return Promise.resolve(null); }
    publishState('loading', {});
    return Promise.all([window.JOMClient.getAdminTruth(), window.JOMClient.getUsersFootprint()]).then(function (results) {
      var payload = { adminTruth: results[0], usersFootprint: results[1] };
      updateOptionalTargets(payload);
      publishState('ready', payload);
      return payload;
    }).catch(function (error) {
      publishState('error', { message: error && error.message ? error.message : 'Admin contract data unavailable' });
      return null;
    });
  }
  function init() { if (!isAdminSurface()) { return; } loadAdminContracts(); }
  window.JOMAdminContractBinding = Object.freeze({ init: init, loadAdminContracts: loadAdminContracts });
  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', init); } else { init(); }
})();

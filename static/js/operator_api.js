(function (window) {
  "use strict";

  const ENDPOINTS = Object.freeze({
    root: "/",
    operatorSummary: "/operator/summary",
    operatorAlerts: "/operator/alerts",
    operatorSurface: "/operator/surface",
    operatorObservability: "/operator/observability",
    runtimeStatus: "/runtime/status",
    runtimeHistory: "/runtime/history",
    runtimeRefresh: "/runtime/refresh",
    health: "/health",
    adminTruth: "/admin/truth",
    estateProductAccess: "/estate/product-access",
    userFootprint: "/users/footprint",
    registrySites: "/registry/sites"
  });

  async function fetchJson(endpoint, options) {
    const response = await fetch(endpoint, Object.assign({
      method: "GET",
      headers: { "Accept": "application/json" },
      cache: "no-store"
    }, options || {}));

    let payload = null;
    try {
      payload = await response.json();
    } catch (error) {
      payload = { error: "Invalid JSON response", detail: String(error) };
    }

    if (!response.ok) {
      const wrapped = {
        ok: false,
        status: response.status,
        endpoint: endpoint,
        payload: payload
      };
      throw wrapped;
    }

    return payload;
  }

  function get(path) {
    return fetchJson(path);
  }

  const api = {
    endpoints: ENDPOINTS,
    fetchJson: fetchJson,
    get: get,
    getRoot: function () { return get(ENDPOINTS.root); },
    getOperatorSummary: function () { return get(ENDPOINTS.operatorSummary); },
    getOperatorAlerts: function () { return get(ENDPOINTS.operatorAlerts); },
    getOperatorSurface: function () { return get(ENDPOINTS.operatorSurface); },
    getOperatorObservability: function () { return get(ENDPOINTS.operatorObservability); },
    getRuntimeStatus: function () { return get(ENDPOINTS.runtimeStatus); },
    getRuntimeHistory: function () { return get(ENDPOINTS.runtimeHistory); },
    runRuntimeRefresh: function () { return get(ENDPOINTS.runtimeRefresh); },
    getHealth: function () { return get(ENDPOINTS.health); },
    getAdminTruth: function () { return get(ENDPOINTS.adminTruth); },
    getEstateProductAccess: function () { return get(ENDPOINTS.estateProductAccess); },
    getUserFootprint: function () { return get(ENDPOINTS.userFootprint); },
    getRegistrySites: function () { return get(ENDPOINTS.registrySites); }
  };

  window.JOMOperatorAPI = api;
})(window);

/* JOM Estate single-owner frontend rebuild v1
 * Owner: static/js/jom_estate_lifecycle_v1.js
 * Contract: /api/workspace/estate
 * Rules: no static dataset path, no legacy JSON, no Command Centre contract dependency.
 */
(function () {
  'use strict';

  var CONTRACT_URL = '/api/workspace/estate';
  var ROOT_SELECTORS = [
    '[data-estate-workspace]',
    '[data-estate-root]',
    '#estate-workspace',
    '#estate-root',
    '#estate-content',
    '.estate-workspace',
    'main'
  ];

  function qs(selector, root) {
    return (root || document).querySelector(selector);
  }

  function escapeHtml(value) {
    if (value === null || value === undefined) {
      return '';
    }
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function numberOrDash(value) {
    if (value === null || value === undefined || value === '') {
      return 'Unavailable';
    }
    return escapeHtml(value);
  }

  function findRoot() {
    for (var i = 0; i < ROOT_SELECTORS.length; i += 1) {
      var found = qs(ROOT_SELECTORS[i]);
      if (found && found !== document.body) {
        return found;
      }
    }
    return document.body;
  }

  function normaliseSites(payload) {
    if (!payload || !Array.isArray(payload.sites)) {
      return [];
    }
    return payload.sites.filter(function (site) {
      return site && typeof site === 'object';
    });
  }

  function sourceHealthItems(payload) {
    var health = payload && payload.source_health && typeof payload.source_health === 'object'
      ? payload.source_health
      : {};
    return Object.keys(health).sort().map(function (key) {
      var item = health[key] || {};
      return {
        key: key,
        available: item.available === undefined ? true : Boolean(item.available),
        type: item.type || 'unknown',
        count: item.count_hint === null || item.count_hint === undefined ? 'n/a' : item.count_hint
      };
    });
  }

  function actionItems(payload) {
    var summary = payload.summary || {};
    var actions = [];
    var reviewItems = Number(summary.review_items || 0);
    var monitoredSites = Number(summary.monitored_sites || 0);
    var totalSites = Number(summary.total_sites || 0);

    if (reviewItems > 0) {
      actions.push({label: 'Review estate items', detail: reviewItems + ' item(s) need review'});
    }
    if (totalSites > 0 && monitoredSites === 0) {
      actions.push({label: 'Monitoring not enabled', detail: 'No discovered sites are currently marked as monitored'});
    }
    if (!actions.length) {
      actions.push({label: 'Estate contract ready', detail: 'No immediate Estate contract blockers detected'});
    }
    return actions;
  }

  function renderSummary(payload) {
    var summary = payload.summary || {};
    return '' +
      '<section class="jom-estate-panel jom-estate-summary" aria-label="Estate summary">' +
        '<h2>Estate workspace</h2>' +
        '<p>Live Estate contract: <code>/api/workspace/estate</code></p>' +
        '<div class="jom-estate-metrics">' +
          '<article class="jom-estate-metric"><span>Total sites</span><strong>' + numberOrDash(summary.total_sites) + '</strong></article>' +
          '<article class="jom-estate-metric"><span>Monitored sites</span><strong>' + numberOrDash(summary.monitored_sites) + '</strong></article>' +
          '<article class="jom-estate-metric"><span>Review items</span><strong>' + numberOrDash(summary.review_items) + '</strong></article>' +
          '<article class="jom-estate-metric"><span>Coverage</span><strong>' + numberOrDash(summary.coverage_percent) + (summary.coverage_percent === null || summary.coverage_percent === undefined ? '' : '%') + '</strong></article>' +
        '</div>' +
      '</section>';
  }

  function renderActions(payload) {
    var actions = actionItems(payload);
    return '' +
      '<section class="jom-estate-panel jom-estate-actions" aria-label="Estate actions">' +
        '<h2>Action required</h2>' +
        '<ul>' + actions.map(function (action) {
          return '<li><strong>' + escapeHtml(action.label) + '</strong><span>' + escapeHtml(action.detail) + '</span></li>';
        }).join('') + '</ul>' +
      '</section>';
  }

  function renderSources(payload) {
    var sources = sourceHealthItems(payload);
    return '' +
      '<section class="jom-estate-panel jom-estate-sources" aria-label="Estate source health">' +
        '<h2>Source health</h2>' +
        '<ul>' + sources.map(function (source) {
          return '<li><strong>' + escapeHtml(source.key) + '</strong><span>' + (source.available ? 'Available' : 'Unavailable') + ' · ' + escapeHtml(source.type) + ' · count ' + escapeHtml(source.count) + '</span></li>';
        }).join('') + '</ul>' +
      '</section>';
  }

  function renderSites(payload) {
    var sites = normaliseSites(payload);
    if (!sites.length) {
      return '' +
        '<section class="jom-estate-panel jom-estate-sites" aria-label="Estate sites">' +
          '<h2>Site inventory</h2>' +
          '<p>No site records were returned by the Estate workspace contract.</p>' +
        '</section>';
    }
    return '' +
      '<section class="jom-estate-panel jom-estate-sites" aria-label="Estate sites">' +
        '<h2>Site inventory</h2>' +
        '<div class="jom-estate-site-list">' + sites.map(function (site) {
          var status = site.status || (site.is_monitored ? 'monitored' : 'discovered');
          var url = site.url ? '<a href="' + escapeHtml(site.url) + '" target="_blank" rel="noopener noreferrer">Open site</a>' : '<span>No site link</span>';
          return '' +
            '<article class="jom-estate-site-card">' +
              '<h3>' + escapeHtml(site.name || site.key || 'Unnamed site') + '</h3>' +
              '<p><strong>Status:</strong> ' + escapeHtml(status) + '</p>' +
              '<p><strong>Key:</strong> ' + escapeHtml(site.key || 'Unavailable') + '</p>' +
              '<p>' + url + '</p>' +
            '</article>';
        }).join('') + '</div>' +
      '</section>';
  }

  function render(payload) {
    var root = findRoot();
    root.innerHTML = '' +
      '<div class="jom-estate-single-owner" data-jom-estate-single-owner="v1">' +
        renderSummary(payload) +
        renderActions(payload) +
        renderSources(payload) +
        renderSites(payload) +
      '</div>';
  }

  function renderError(error) {
    var root = findRoot();
    root.innerHTML = '' +
      '<section class="jom-estate-panel jom-estate-error" role="alert">' +
        '<h2>Estate workspace unavailable</h2>' +
        '<p>The Estate workspace contract could not be loaded.</p>' +
        '<pre>' + escapeHtml(error && error.message ? error.message : error) + '</pre>' +
      '</section>';
  }

  function loadEstate() {
    fetch(CONTRACT_URL, {headers: {'Accept': 'application/json'}, credentials: 'same-origin'})
      .then(function (response) {
        if (!response.ok) {
          throw new Error('Estate workspace contract returned HTTP ' + response.status);
        }
        return response.json();
      })
      .then(function (payload) {
        render(payload || {});
      })
      .catch(renderError);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadEstate);
  } else {
    loadEstate();
  }
}());

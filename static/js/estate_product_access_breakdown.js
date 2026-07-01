/*
 * JOM LEGACY JS ADAPTER MIGRATION EXECUTION PACK v1
 * File: static\js\estate_product_access_breakdown.js
 * Target endpoints: /estate/product-access + /registry/sites
 * Purpose: mark this module as part of the controlled legacy-to-operator adapter migration.
 * Behaviour safety: no visual, template, or CSS changes are made by this pack.
 * Compatibility routes remain active while endpoint-specific payload alignment is completed.
 */
(function () {
  function number(value) {
    const parsed = Number(value || 0);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function formatNumber(value) {
    return number(value).toLocaleString();
  }

  function setText(id, value) {
    const element = document.getElementById(id);
    if (element) element.textContent = value;
  }

  function normalise(value) {
    return String(value || '')
      .toLowerCase()
      .trim()
      .replace(/^https?:\/\//, '')
      .replace(/\.atlassian\.net.*$/, '')
      .replace(/\/$/, '');
  }

  function tokensFor(record) {
    const tokens = [];
    ['site_key', 'site_name', 'site_url', 'cloud_id', 'url'].forEach(function (field) {
      if (record && record[field]) tokens.push(normalise(record[field]));
    });
    if (record && Array.isArray(record.aliases)) {
      record.aliases.forEach(function (alias) { tokens.push(normalise(alias)); });
    }
    return Array.from(new Set(tokens.filter(Boolean)));
  }

  function statusLabel(row) {
    const status = String(row.status || '').toLowerCase();
    if (status === 'ok') return 'Confirmed';
    if (status === 'error') return 'Blocked';
    return status || 'Unknown';
  }

  function statusClass(row) {
    const status = String(row.status || '').toLowerCase();
    if (status === 'ok') return 'product-access-badge--ok';
    if (status === 'error') return 'product-access-badge--blocked';
    return 'product-access-badge--neutral';
  }

  function createTextCell(value) {
    const cell = document.createElement('td');
    cell.textContent = value;
    return cell;
  }

  function createSiteCell(siteName, siteKey) {
    const cell = document.createElement('td');
    const strong = document.createElement('strong');
    strong.textContent = siteName || 'Unknown site';
    const small = document.createElement('small');
    small.textContent = siteKey || '';
    cell.appendChild(strong);
    cell.appendChild(small);
    return cell;
  }

  function createStatusCell(site) {
    const cell = document.createElement('td');
    const badge = document.createElement('span');
    badge.className = 'product-access-badge ' + statusClass(site);
    badge.textContent = statusLabel(site);
    cell.appendChild(badge);
    return cell;
  }

  function isMonitoredRecord(record, monitoredTokens) {
    const recordTokens = tokensFor(record);
    return recordTokens.some(function (token) { return monitoredTokens.has(token); });
  }

  function monitoredTokensFromRegistry(registry) {
    const sites = Array.isArray(registry && registry.sites) ? registry.sites : [];
    const tokens = new Set();
    sites
      .filter(function (site) { return site.classification === 'monitored'; })
      .forEach(function (site) {
        tokensFor(site).forEach(function (token) { tokens.add(token); });
      });
    return tokens;
  }

  function buildScopedPayload(productAccess, registry) {
    const monitoredTokens = monitoredTokensFromRegistry(registry);
    const sourceSites = Array.isArray(productAccess.sites) ? productAccess.sites : [];
    const sourceRoles = Array.isArray(productAccess.roles) ? productAccess.roles : [];

    const scopedSites = sourceSites.filter(function (site) {
      return isMonitoredRecord(site, monitoredTokens);
    });
    const scopedRoles = sourceRoles.filter(function (role) {
      return isMonitoredRecord(role, monitoredTokens);
    });

    const confirmedSites = scopedSites.filter(function (site) {
      return String(site.status || '').toLowerCase() === 'ok';
    });
    const blockedSites = scopedSites.filter(function (site) {
      return String(site.status || '').toLowerCase() === 'error';
    });

    return {
      summary: {
        sites_with_jira_roles: confirmedSites.length,
        total_jira_product_user_count: scopedSites.reduce(function (total, site) {
          return total + number(site.jira_product_user_count);
        }, 0),
        accessible_jira_resource_count: scopedSites.length,
        error_site_count: blockedSites.length,
        jira_role_rows: scopedRoles.length
      },
      sites: scopedSites,
      roles: scopedRoles
    };
  }

  function renderSites(payload) {
    const body = document.getElementById('estate-product-access-body');
    const empty = document.getElementById('estate-product-access-empty');
    if (!body) return;

    const sites = Array.isArray(payload.sites) ? payload.sites.slice() : [];
    body.innerHTML = '';

    if (!sites.length) {
      if (empty) empty.style.display = 'block';
      return;
    }

    if (empty) empty.style.display = 'none';

    sites.sort(function (a, b) {
      const aUsers = number(a.jira_product_user_count);
      const bUsers = number(b.jira_product_user_count);
      if (bUsers !== aUsers) return bUsers - aUsers;
      return String(a.site_key || '').localeCompare(String(b.site_key || ''));
    });

    sites.forEach(function (site) {
      const row = document.createElement('tr');
      const userCount = number(site.jira_product_user_count);
      const roleCount = number(site.jira_role_count);
      const siteName = site.site_name || site.site_key || 'Unknown site';
      const siteKey = site.site_key || '';

      row.appendChild(createSiteCell(siteName, siteKey));
      row.appendChild(createTextCell(formatNumber(userCount)));
      row.appendChild(createTextCell(formatNumber(roleCount)));
      row.appendChild(createStatusCell(site));
      body.appendChild(row);
    });
  }

  function renderRoles(payload) {
    const body = document.getElementById('estate-product-access-role-body');
    if (!body) return;

    const roles = Array.isArray(payload.roles) ? payload.roles.slice() : [];
    body.innerHTML = '';

    roles.sort(function (a, b) {
      return number(b.user_count) - number(a.user_count);
    });

    roles.forEach(function (role) {
      const row = document.createElement('tr');
      row.appendChild(createSiteCell(role.site_name || role.site_key || 'Unknown site', role.role_name || role.role_key || 'Jira role'));
      row.appendChild(createTextCell(formatNumber(role.user_count)));
      row.appendChild(createTextCell(formatNumber(role.seat_limit)));
      row.appendChild(createTextCell(formatNumber(role.remaining_seats)));
      body.appendChild(row);
    });
  }

  function render(payload) {
    const summary = payload.summary || {};
    setText('product-access-site-count', formatNumber(summary.sites_with_jira_roles));
    setText('product-access-api-users', formatNumber(summary.total_jira_product_user_count));
    setText('product-access-resource-count', formatNumber(summary.accessible_jira_resource_count));
    setText('product-access-error-count', formatNumber(summary.error_site_count));
    renderSites(payload);
    renderRoles(payload);
  }

  function fetchJson(url) {
    return fetch(url, { cache: 'no-store' }).then(function (response) {
      if (!response.ok) throw new Error(url + ' unavailable');
      return response.json();
    });
  }

  function init() {
    const root = document.getElementById('estate-product-access-breakdown');
    if (!root) return;

    Promise.all([
      fetchJson('/static/data/estate_product_access.json'),
      fetchJson('/api/site-registry').catch(function () { return fetchJson('/static/data/site_registry.json'); })
    ])
      .then(function (results) {
        render(buildScopedPayload(results[0] || {}, results[1] || {}));
      })
      .catch(function () {
        render({ summary: {}, sites: [], roles: [] });
      });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();

function jomLegacyAdapterMigrationNoteV1() {
  return {
    phase: "legacy-js-adapter-migration-execution-v1",
    behaviour: "compatibility routes remain active until payload-specific adapter swaps are validated",
    uiChanges: false,
    cssChanges: false,
    templateChanges: false
  };
}

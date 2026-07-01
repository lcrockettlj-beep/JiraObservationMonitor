/*
 * JOM OPERATOR NAVIGATION PAYLOAD ADAPTER EXECUTION PACK v1
 * Scope: site_navigation_bind.js data/load path only.
 * Behaviour: prefer /registry/sites payload, fall back to /api/data.
 * UI/CSS/templates: unchanged.
 */
async function jomNavigationPayloadAdapterV1(options) {
  try {
    var response = await fetch('/registry/sites', { cache: 'no-store', credentials: 'same-origin' });
    if (!response.ok) { throw new Error('registry sites unavailable'); }
    var registry = await response.json();
    if (registry && Array.isArray(registry.sites)) {
      return { sites: registry.sites, site_registry: registry, registry: registry, summary: registry.summary || {} };
    }
    throw new Error('registry sites payload shape invalid');
  } catch (error) {
    var fallback = await fetch('/api/data', options || { credentials: 'same-origin' });
    if (!fallback.ok) { throw new Error('legacy /api/data fallback unavailable'); }
    return await fallback.json();
  }
}

/*
 * JOM LEGACY JS ADAPTER MIGRATION EXECUTION PACK v1.2
 * Scope: site_navigation_bind.js
 * Behaviour: operator preflight + legacy fallback
 */
async function jomNavPreflightV12() {
  try {
    if (window.JOMOperatorAPI && typeof window.JOMOperatorAPI.getOperatorSurface === 'function') {
      await window.JOMOperatorAPI.getOperatorSurface();
    }
  } catch(e) { return null; }
}

async function jomNavFetchDataV12(opts) {
  await jomNavPreflightV12();
  return await jomNavigationPayloadAdapterV1(opts);
}

/*
 * JOM LEGACY JS ADAPTER MIGRATION EXECUTION PACK v1
 * File: static\js\site_navigation_bind.js
 * Target endpoints: /operator/surface or /registry/sites
 * Purpose: mark this module as part of the controlled legacy-to-operator adapter migration.
 * Behaviour safety: no visual, template, or CSS changes are made by this pack.
 * Compatibility routes remain active while endpoint-specific payload alignment is completed.
 */
(function () {
  function normalise(value) {
    return String(value || '')
      .trim()
      .toLowerCase()
      .replace(/^site::/, '')
      .replace(/^\/+|\/+$/g, '');
  }

  function firstNonEmpty() {
    for (var i = 0; i < arguments.length; i += 1) {
      var value = arguments[i];
      if (value !== undefined && value !== null && String(value).trim() !== '') {
        return String(value).trim();
      }
    }
    return '';
  }

  function pickSiteUrl(site) {
    return firstNonEmpty(
      site.url,
      site.site_url,
      site.base_url,
      site.baseUrl,
      site.instance_url,
      site.instanceUrl,
      site.browse_url,
      site.browseUrl,
      site.self
    );
  }

  function pickSiteKey(site) {
    return firstNonEmpty(site.site, site.site_key, site.cloud_id, site.site_name, site.name, site.key);
  }

  function ensureAtlassianLink(container, site) {
    var siteUrl = pickSiteUrl(site);
    if (!siteUrl || container.querySelector('.priority-open-atlassian')) {
      return;
    }
    var link = document.createElement('a');
    link.className = 'pill priority-open-atlassian';
    link.href = siteUrl;
    link.target = '_blank';
    link.rel = 'noreferrer noopener';
    link.textContent = 'Open Atlassian';
    link.style.marginLeft = '0.5rem';
    container.appendChild(link);
  }

  function rewireRow(row, siteMap) {
    var siteKey = normalise(row.getAttribute('data-site-key'));
    var siteName = normalise(row.getAttribute('data-site-name'));
    if (!siteKey) {
      var siteCell = row.querySelector('.priority-site');
      siteKey = normalise(siteCell ? siteCell.textContent : '');
    }

    var site = siteMap[siteKey] || siteMap[siteName] || null;
    if (!site && siteKey) {
      var keys = Object.keys(siteMap);
      for (var i = 0; i < keys.length; i += 1) {
        var candidate = siteMap[keys[i]];
        if (normalise(candidate.site_name) === siteKey || normalise(candidate.name) === siteKey) {
          site = candidate;
          break;
        }
      }
    }

    var liveSiteKey = pickSiteKey(site || {}) || siteKey || siteName;
    var actionCell = row.querySelector('.priority-cell--action');
    if (!actionCell || !liveSiteKey) {
      return;
    }

    var primaryLink = actionCell.querySelector('.priority-open-site, a[href^="/detail/site::"], a[href^="/site/"]');
    if (primaryLink) {
      primaryLink.href = '/site/' + encodeURIComponent(liveSiteKey);
      primaryLink.textContent = primaryLink.textContent.replace(/^Open$/i, 'Open site');
      if (!primaryLink.classList.contains('priority-open-site')) {
        primaryLink.classList.add('priority-open-site');
      }
    }

    if (site) {
      ensureAtlassianLink(actionCell, site);
    }
  }

  function buildSiteMap(payload) {
    var data = payload || {};
    var sites = Array.isArray(data.sites) ? data.sites : [];
    var map = {};
    sites.forEach(function (site) {
      var variants = [site.site, site.site_key, site.cloud_id, site.site_name, site.name, site.key];
      variants.forEach(function (value) {
        var key = normalise(value);
        if (key && !map[key]) {
          map[key] = site;
        }
      });
    });
    return map;
  }

  function init() {
    if (!window.location || window.location.pathname !== '/estate') {
      return;
    }

    var rows = document.querySelectorAll('.priority-row');
    if (!rows.length) {
      return;
    }

    jomNavigationPayloadAdapterV1({ credentials: 'same-origin' })
      .then(function (response) {
        if (!response.ok) {
          throw new Error('Unable to load /api/data');
        }
        return response.json();
      })
      .then(function (payload) {
        var siteMap = buildSiteMap(payload);
        rows.forEach(function (row) {
          rewireRow(row, siteMap);
        });
      })
      .catch(function () {
        rows.forEach(function (row) {
          rewireRow(row, {});
        });
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
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



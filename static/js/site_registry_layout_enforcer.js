(function () {
  const APPROVED_FALLBACK = ['gli-delivery-tm', 'gli-global-technology', 'gli-it-project'];

  function norm(value) {
    return String(value || '')
      .toLowerCase()
      .trim()
      .replace(/^https?:\/\//, '')
      .replace(/\.atlassian\.net.*$/, '')
      .replace(/\/$/, '');
  }

  function esc(value) {
    return String(value == null ? '' : value).replace(/[&<>\"]/g, function (char) {
      return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[char];
    });
  }

  function tokensFor(site) {
    const tokens = [];
    ['site_key', 'site_name', 'site_url', 'cloud_id'].forEach(function (key) {
      if (site && site[key]) tokens.push(norm(site[key]));
    });
    if (site && Array.isArray(site.aliases)) {
      site.aliases.forEach(function (alias) { tokens.push(norm(alias)); });
    }
    return Array.from(new Set(tokens.filter(Boolean)));
  }

  function pageMode() {
    if (location.pathname.indexOf('/admin') === 0) return 'admin';
    if (location.pathname.indexOf('/estate') === 0) return 'estate';
    return 'home';
  }

  function textMatchesAny(text, tokens) {
    const normalised = norm(text);
    return tokens.some(function (token) { return token && normalised.indexOf(token) >= 0; });
  }

  function getHeadingText(element) {
    return String((element && element.textContent) || '').toLowerCase().replace(/\s+/g, ' ').trim();
  }

  function findPanelByExactHeading(label) {
    const desired = label.toLowerCase();
    const headings = Array.from(document.querySelectorAll('h1,h2,h3,h4'));
    for (const heading of headings) {
      const text = getHeadingText(heading);
      if (text === desired || text.indexOf(desired) >= 0) {
        let node = heading;
        while (node && node !== document.body) {
          const className = String(node.className || '');
          if (
            node.tagName === 'SECTION' ||
            className.match(/panel|card|section|registry|board|sites|surface|group/i)
          ) {
            return node;
          }
          node = node.parentElement;
        }
      }
    }
    return null;
  }

  function findSitePriorityBoard() {
    return findPanelByExactHeading('site prioritisation board') || findPanelByExactHeading('site prioritization board');
  }

  function siteLikeCardCandidates(section) {
    if (!section) return [];
    return Array.from(section.querySelectorAll('tr, article, .card, .site-card, .site-tile, [class*="site"]'))
      .filter(function (element) {
        if (element.querySelector && element.querySelector('th')) return false;
        const text = String(element.textContent || '');
        if (!text.trim()) return false;
        return /open site|open atlassian|site signals|site projects|safe mode|low risk|stable|atlassian\.net/i.test(text);
      });
  }

  function updateSitesBadge(section, count) {
    if (!section) return;
    const candidates = Array.from(section.querySelectorAll('span,button,div'));
    for (const element of candidates) {
      const text = String(element.textContent || '').trim();
      if (/^\d+\s+sites?$/i.test(text)) {
        element.textContent = count + ' sites';
        return;
      }
    }
  }

  function filterSectionToMonitored(section, monitoredTokens) {
    if (!section) return 0;
    const candidates = siteLikeCardCandidates(section);
    let visibleCount = 0;
    candidates.forEach(function (element) {
      const text = element.textContent || '';
      if (textMatchesAny(text, monitoredTokens)) {
        element.style.display = '';
        visibleCount += 1;
      } else {
        element.style.display = 'none';
      }
    });
    if (visibleCount > 0) updateSitesBadge(section, visibleCount);
    return visibleCount;
  }

  function renderDiscoveredPanel(discoveredSites, summary) {
    let html = '';
    html += '<div class="site-registry-head">';
    html += '<div><h2>Discovered Sites Awaiting Review</h2>';
    html += '<p>These Jira resources were discovered from Atlassian Admin/Billing signals but are not monitored until approved.</p></div>';
    html += '<div class="site-registry-summary"><span>Discovered <b>' + esc(discoveredSites.length) + '</b></span><span>Pending onboarding <b>' + esc(summary.pending_onboarding_count || 0) + '</b></span></div>';
    html += '</div>';

    if (!discoveredSites.length) {
      html += '<p class="site-registry-note">No discovered Jira resources are waiting for approval.</p>';
      return html;
    }

    html += '<div class="site-registry-table-wrap"><table class="site-registry-table"><thead><tr><th>Site</th><th>URL / Cloud ID</th><th>Status</th><th>Collector</th><th>Signals</th></tr></thead><tbody>';
    discoveredSites.forEach(function (site) {
      const signals = [];
      if (site.metrics && site.metrics.jira_product_user_count != null) signals.push('Product users: ' + site.metrics.jira_product_user_count);
      if (site.metrics && site.metrics.named_access_count != null) signals.push('Named direct: ' + site.metrics.named_access_count);
      if (site.sources) signals.push('Sources: ' + site.sources.join(', '));
      html += '<tr>';
      html += '<td><strong>' + esc(site.site_name || site.site_key || site.cloud_id) + '</strong><small>' + esc(site.site_key || '') + '</small></td>';
      html += '<td>' + esc(site.site_url || site.cloud_id || 'Unknown') + '</td>';
      html += '<td><span class="site-registry-badge site-registry-badge--discovered">Discovered</span></td>';
      html += '<td>' + esc(site.collector_onboarding_status || 'not_requested') + '</td>';
      html += '<td>' + esc(signals.join(' | ')) + '</td>';
      html += '</tr>';
    });
    html += '</tbody></table></div>';
    html += '<p class="site-registry-note">Approval is controlled from Admin and creates a collector-onboarding trigger before full monitoring is trusted.</p>';
    return html;
  }

  function placeDiscoveryBelowStable(discoveredSites, summary) {
    const stablePanel = findPanelByExactHeading('stable sites');
    if (!stablePanel || !stablePanel.parentElement) return;

    document.querySelectorAll('#home-site-registry-mount, #home-site-discovery-mount').forEach(function (element) {
      element.remove();
    });

    const panel = document.createElement('section');
    panel.id = 'home-site-discovery-mount';
    panel.className = 'site-registry-panel site-registry-panel--discovery';
    panel.innerHTML = renderDiscoveredPanel(discoveredSites, summary);
    stablePanel.parentElement.insertBefore(panel, stablePanel.nextSibling);
  }

  function removeEstateDiscoveryPanel() {
    document.querySelectorAll('#estate-site-registry-mount, #home-site-registry-mount').forEach(function (element) {
      element.remove();
    });
  }

  function enforceRegistry(data) {
    const mode = pageMode();
    const sites = Array.isArray(data.sites) ? data.sites : [];
    const summary = data.summary || {};
    const monitoredSites = sites.filter(function (site) { return site.classification === 'monitored'; });
    const discoveredSites = sites.filter(function (site) { return site.classification === 'discovered'; });
    let monitoredTokens = [];

    monitoredSites.forEach(function (site) {
      monitoredTokens = monitoredTokens.concat(tokensFor(site));
    });

    if (!monitoredTokens.length) monitoredTokens = APPROVED_FALLBACK.slice();
    monitoredTokens = Array.from(new Set(monitoredTokens.filter(Boolean)));

    if (mode === 'home') {
      filterSectionToMonitored(findPanelByExactHeading('stable sites'), monitoredTokens);
      placeDiscoveryBelowStable(discoveredSites, summary);
    }

    if (mode === 'estate') {
      removeEstateDiscoveryPanel();
      filterSectionToMonitored(findSitePriorityBoard(), monitoredTokens);
    }
  }

  function run() {
    fetch('/api/site-registry', { cache: 'no-store' })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        enforceRegistry(data);
        let attempts = 0;
        const timer = setInterval(function () {
          attempts += 1;
          enforceRegistry(data);
          if (attempts >= 8) clearInterval(timer);
        }, 750);
      })
      .catch(function () {});
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', run);
  else run();
})();

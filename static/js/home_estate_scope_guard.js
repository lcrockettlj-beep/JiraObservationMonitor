(function () {
  const APPROVED = ['gli-delivery-tm', 'gli-global-technology', 'gli-it-project'];
  const DISCOVERY_WORDS = ['discovered sites awaiting review', 'all jira sites & new discoveries', 'site discovery'];

  function norm(value) {
    return String(value || '')
      .toLowerCase()
      .trim()
      .replace(/^https?:\/\//, '')
      .replace(/\.atlassian\.net.*$/, '')
      .replace(/\/$/, '');
  }

  function pageMode() {
    if (location.pathname.indexOf('/estate') === 0) return 'estate';
    if (location.pathname.indexOf('/admin') === 0) return 'admin';
    return 'home';
  }

  function text(element) {
    return String((element && element.textContent) || '').toLowerCase().replace(/\s+/g, ' ').trim();
  }

  function includesApprovedSite(value) {
    const normalized = norm(value);
    return APPROVED.some(function (key) {
      return normalized.indexOf(key) >= 0;
    });
  }

  function removeElement(element) {
    if (element && element.parentNode) element.parentNode.removeChild(element);
  }

  function nearestLargePanel(element) {
    let node = element;
    while (node && node !== document.body) {
      const cls = String(node.className || '');
      if (node.tagName === 'SECTION' || cls.match(/panel|card|surface|registry|board|sites|group|section/i)) {
        return node;
      }
      node = node.parentElement;
    }
    return element;
  }

  function removeDiscoveryPanels() {
    ['home-site-registry-mount', 'home-site-discovery-mount', 'estate-site-registry-mount', 'admin-site-registry-mount'].forEach(function (id) {
      if (pageMode() !== 'admin' || id !== 'admin-site-registry-mount') {
        removeElement(document.getElementById(id));
      }
    });

    Array.from(document.querySelectorAll('h1,h2,h3,h4')).forEach(function (heading) {
      const headingText = text(heading);
      if (DISCOVERY_WORDS.some(function (word) { return headingText.indexOf(word) >= 0; })) {
        const panel = nearestLargePanel(heading);
        if (panel && panel !== document.body) removeElement(panel);
      }
    });
  }

  function findPanelByHeading(label) {
    const want = label.toLowerCase();
    const headings = Array.from(document.querySelectorAll('h1,h2,h3,h4'));
    for (const heading of headings) {
      if (text(heading).indexOf(want) >= 0) return nearestLargePanel(heading);
    }
    return null;
  }

  function updateSiteCount(panel) {
    if (!panel) return;
    Array.from(panel.querySelectorAll('span,button,div')).some(function (node) {
      if (/^\d+\s+sites?$/i.test(String(node.textContent || '').trim())) {
        node.textContent = '3 sites';
        return true;
      }
      return false;
    });
  }

  function siteRows(panel) {
    if (!panel) return [];
    return Array.from(panel.querySelectorAll('tr, article, .card, .site-card, .site-tile, [class*="site"]')).filter(function (node) {
      if (node.querySelector && node.querySelector('th')) return false;
      const nodeText = text(node);
      if (!nodeText) return false;
      return /gaminglabs-|gli-|atlassian\.net|open site|open atlassian|site signals|site projects|safe mode/i.test(nodeText);
    });
  }

  function filterPanel(panel) {
    if (!panel) return;
    let visible = 0;
    siteRows(panel).forEach(function (row) {
      if (includesApprovedSite(row.textContent)) {
        row.style.display = '';
        visible += 1;
      } else {
        row.style.display = 'none';
      }
    });
    updateSiteCount(panel);
  }

  function stabiliseHome() {
    removeDiscoveryPanels();
    filterPanel(findPanelByHeading('stable sites'));
  }

  function stabiliseEstate() {
    removeDiscoveryPanels();
    filterPanel(findPanelByHeading('site prioritisation board') || findPanelByHeading('site prioritization board'));
  }

  function run() {
    if (pageMode() === 'admin') return;
    if (pageMode() === 'estate') stabiliseEstate();
    else stabiliseHome();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', run);
  else run();

  let attempts = 0;
  const timer = setInterval(function () {
    attempts += 1;
    run();
    if (attempts >= 12) clearInterval(timer);
  }, 500);
})();

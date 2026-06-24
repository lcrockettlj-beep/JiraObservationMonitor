(function () {
  const PATH_OK = window.location && window.location.pathname === '/estate';
  if (!PATH_OK) return;

  function normalise(value) {
    return String(value || '').trim().toLowerCase();
  }

  function safeSlug(value) {
    return String(value || '').trim();
  }

  function ensureActionsHost(card) {
    let host = card.querySelector('.jom-site-nav-links');
    if (host) return host;
    host = document.createElement('div');
    host.className = 'jom-site-nav-links';
    host.style.display = 'flex';
    host.style.flexWrap = 'wrap';
    host.style.gap = '8px';
    host.style.marginTop = '12px';
    card.appendChild(host);
    return host;
  }

  function buildAnchor(href, text) {
    const a = document.createElement('a');
    a.href = href;
    a.className = 'pill';
    a.textContent = text;
    return a;
  }

  function matchCardToSite(card, sites) {
    const text = normalise(card.innerText || card.textContent || '');
    if (!text) return null;
    for (const site of sites) {
      const candidates = [
        site.site,
        site.site_key,
        site.site_name,
        site.name,
        site.url,
      ].map(normalise).filter(Boolean);
      if (candidates.some(c => text.includes(c))) {
        return site;
      }
    }
    return null;
  }

  async function run() {
    try {
      const res = await fetch('/api/data', { credentials: 'same-origin' });
      if (!res.ok) return;
      const payload = await res.json();
      const sites = Array.isArray(payload.sites) ? payload.sites : [];
      if (!sites.length) return;

      const selectors = [
        '.estate-site-card',
        '.estate-card',
        '.site-card',
        '.signal-border',
        '.panel',
        'article',
      ];
      const cards = Array.from(document.querySelectorAll(selectors.join(',')));
      if (!cards.length) return;

      cards.forEach((card) => {
        if (card.querySelector('[data-jom-site-link="true"]')) return;
        const site = matchCardToSite(card, sites);
        if (!site) return;
        const key = safeSlug(site.site || site.site_key || site.cloud_id);
        if (!key) return;

        const host = ensureActionsHost(card);
        if (!host.querySelector(`[href="/site/${CSS.escape(key)}"]`)) {
          const siteLink = buildAnchor(`/site/${encodeURIComponent(key)}`, 'Open site');
          siteLink.setAttribute('data-jom-site-link', 'true');
          host.appendChild(siteLink);
        }
        if (site.url && !host.querySelector(`[href="${site.url}"]`)) {
          const ext = buildAnchor(site.url, 'Open Atlassian');
          ext.target = '_blank';
          ext.rel = 'noopener noreferrer';
          ext.setAttribute('data-jom-site-link', 'true');
          host.appendChild(ext);
        }
      });
    } catch (err) {
      console.warn('JOM site navigation bind skipped:', err);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', run, { once: true });
  } else {
    run();
  }
})();

(() => {
  const $ = (id) => document.getElementById(id);
  const fmt = (v) => v === null || v === undefined || v === '' ? '--' : String(v);
  const safeArray = (v) => Array.isArray(v) ? v : [];
  const set = (id, value) => { const el = $(id); if (el) el.textContent = fmt(value); };
  const esc = (value) => String(value ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  async function getJson(path) {
    const res = await fetch(path, { cache: 'no-store' });
    if (!res.ok) throw new Error(`${path} returned ${res.status}`);
    return res.json();
  }
  function bindNav() {
    const btn = $('jom-nav-toggle'); const nav = $('jom-side-nav'); const backdrop = $('jom-nav-backdrop');
    if (!btn || !nav || !backdrop) return;
    const open = () => { nav.classList.add('jom-side-nav--open'); backdrop.hidden = false; btn.setAttribute('aria-expanded','true'); };
    const close = () => { nav.classList.remove('jom-side-nav--open'); backdrop.hidden = true; btn.setAttribute('aria-expanded','false'); };
    btn.addEventListener('click', () => nav.classList.contains('jom-side-nav--open') ? close() : open());
    backdrop.addEventListener('click', close);
  }
  function siteName(site) { return site.site_name || site.site_key || site.key || site.cloud_id || 'Unknown site'; }
  function siteUrl(site) { return site.site_url || site.url || site.cloud_id || ''; }
  function signals(site) {
    const out = [];
    if (site.metrics?.jira_product_user_count !== undefined) out.push(`Product users: ${site.metrics.jira_product_user_count}`);
    if (site.metrics?.named_access_count !== undefined) out.push(`Named direct: ${site.metrics.named_access_count}`);
    if (Array.isArray(site.sources)) out.push(`Sources: ${site.sources.join(', ')}`);
    return out.join(' | ') || 'No signal details available';
  }
  function renderDiscovery(registry) {
    const body = $('discovery-body'); if (!body) return;
    const sites = safeArray(registry.sites);
    const discovered = sites.filter(s => String(s.classification || '').toLowerCase() !== 'monitored');
    if (!discovered.length) { body.innerHTML = '<tr><td colspan="4">No discovered sites awaiting review.</td></tr>'; return; }
    body.innerHTML = discovered.map(site => `<tr><td><strong>${esc(siteName(site))}</strong><br><small>${esc(site.site_key || '')}</small></td><td>${esc(siteUrl(site))}</td><td><span class="jom-status">${esc(site.classification || 'discovered')}</span></td><td>${esc(signals(site))}</td></tr>`).join('');
  }
  function calcHealth({ summary, alerts, registry }) {
    const alertCount = Number(alerts.alert_count ?? alerts.count ?? 0) || 0;
    const sites = safeArray(registry.sites);
    const discovered = sites.filter(s => String(s.classification || '').toLowerCase() !== 'monitored').length;
    const monitored = sites.filter(s => String(s.classification || '').toLowerCase() === 'monitored').length;
    const runtimeOk = /ok|healthy|stable|success/i.test(JSON.stringify(summary));
    let score = 100 - (alertCount * 8) - (discovered > 0 ? 4 : 0) - (!runtimeOk ? 8 : 0);
    score = Math.max(0, Math.min(100, score));
    return { score, alertCount, discovered, monitored, total: sites.length, runtimeOk };
  }
  function renderBrief(facts) {
    const list = $('ai-brief-list'); if (!list) return;
    const items = [];
    items.push(facts.runtimeOk ? 'Runtime contract is responding and no runtime failure was detected from the summary payload.' : 'Runtime contract returned data, but runtime state should be reviewed.');
    items.push(facts.alertCount > 0 ? `${facts.alertCount} active alert signal is present.` : 'No active alert signals are present.');
    items.push(facts.discovered > 0 ? `${facts.discovered} discovered sites require Admin review before monitoring approval.` : 'No discovered sites are waiting for Admin review.');
    items.push(`${facts.monitored} sites are currently in monitored operational scope.`);
    list.innerHTML = items.map(i => `<li>${esc(i)}</li>`).join('');
  }
  async function init() {
    bindNav();
    try {
      const [summary, alerts, registry, footprint] = await Promise.all([
        getJson('/operator/summary').catch(() => ({})),
        getJson('/operator/alerts').catch(() => ({})),
        getJson('/registry/sites').catch(() => ({})),
        getJson('/users/footprint').catch(() => ({})),
      ]);
      const facts = calcHealth({ summary, alerts, registry });
      const users = Array.isArray(footprint.users) ? footprint.users.length : Array.isArray(footprint.rows) ? footprint.rows.length : footprint.user_count ?? footprint.total_users ?? '--';
      set('metric-sites', facts.total);
      set('metric-monitored', facts.monitored);
      set('metric-discovered', facts.discovered);
      set('metric-users', users);
      set('metric-alerts', facts.alertCount);
      set('metric-runtime', facts.runtimeOk ? 'OK' : 'Review');
      set('runtime-status', facts.runtimeOk ? 'OK' : 'Review');
      set('source-health', 'Review');
      set('alert-count', facts.alertCount);
      set('risk-critical', 0);
      set('risk-warning', facts.alertCount + facts.discovered > 0 ? 1 : 0);
      set('risk-stable', facts.monitored);
      set('risk-total-pill', `${facts.total} sites`);
      set('jom-health-score', `${facts.score}%`);
      const bar = $('jom-health-score-bar'); if (bar) bar.style.width = `${facts.score}%`;
      set('jom-health-note', facts.discovered > 0 ? 'Discovery queue is active.' : 'No discovery queue pressure.');
      renderDiscovery(registry);
      renderBrief(facts);
      const json = $('command-json'); if (json) json.textContent = JSON.stringify({ summary, alerts, registry_summary: registry.summary || {}, health_score: facts.score }, null, 2);
    } catch (err) {
      set('runtime-status', 'Review');
      const list = $('ai-brief-list'); if (list) list.innerHTML = `<li>Command Centre failed to load one or more live contracts: ${esc(err.message)}</li>`;
    }
  }
  document.addEventListener('DOMContentLoaded', init);
})();
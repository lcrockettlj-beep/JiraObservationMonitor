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

/* === Command Centre Visual Polish v1 START === */
(() => {
  function pad(n){ return String(n).padStart(2, '0'); }
  function stamp(){
    const d = new Date();
    return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  }
  function setText(id, value){
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  }
  function initPolish(){
    setText('jom-last-refresh', stamp());
    setText('jom-auto-refresh-state', 'Live');
    setText('jom-command-env', 'Local Dev');
    setText('jom-env-label', 'Local Dev');
    setText('jom-command-build', 'Command Centre v1');
    setText('jom-build-label', 'Command Centre v1');
    window.addEventListener('focus', () => setText('jom-last-refresh', stamp()));
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initPolish);
  else initPolish();
})();
/* === Command Centre Visual Polish v1 END === */

/* === Estate Foundation Build v1 START === */
(() => {
  const $ = (id) => document.getElementById(id);
  const safeArray = (value) => Array.isArray(value) ? value : [];
  const esc = (value) => String(value ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const setText = (id, value) => { const el = $(id); if (el) el.textContent = value === undefined || value === null || value === '' ? '--' : String(value); };
  async function getJson(path) {
    const response = await fetch(path, { cache: 'no-store' });
    if (!response.ok) throw new Error(`${path} returned ${response.status}`);
    return response.json();
  }
  function siteName(site) { return site.site_name || site.site_key || site.key || site.cloud_id || 'Unknown site'; }
  function siteUrl(site) { return site.site_url || site.url || site.cloud_id || ''; }
  function classification(site) { return String(site.classification || site.status || 'discovered').toLowerCase(); }
  function productUsers(site) { return site.metrics?.jira_product_user_count ?? site.jira_product_user_count ?? site.product_users ?? '--'; }
  function namedAccess(site) { return site.metrics?.named_access_count ?? site.named_access_count ?? '--'; }
  function signals(site) {
    const output = [];
    if (productUsers(site) !== '--') output.push(`Product users: ${productUsers(site)}`);
    if (namedAccess(site) !== '--') output.push(`Named direct: ${namedAccess(site)}`);
    if (Array.isArray(site.sources)) output.push(`Sources: ${site.sources.join(', ')}`);
    return output.join(' | ') || 'No signal details available';
  }
  function risk(site) {
    return classification(site) === 'monitored' ? 'Normal' : 'Review';
  }
  function statusBadge(site) {
    const cls = classification(site);
    return `<span class="jom-status ${cls === 'monitored' ? 'jom-status--monitored' : ''}">${esc(cls)}</span>`;
  }
  function row(site, index) {
    const cls = classification(site);
    const isReview = cls !== 'monitored';
    return `<tr data-index="${index}" data-classification="${esc(cls)}"><td><span class="jom-health-dot ${isReview ? 'jom-health-dot--review' : ''}">${isReview ? 'Review' : 'Normal'}</span></td><td><strong>${esc(siteName(site))}</strong><br><small>${esc(siteUrl(site))}</small></td><td>${esc(productUsers(site))}</td><td>${esc(namedAccess(site))}</td><td>${esc(risk(site))}</td><td>${statusBadge(site)}</td></tr>`;
  }
  function renderDetail(site) {
    setText('estate-detail-title', siteName(site));
    setText('estate-detail-url', siteUrl(site) || 'No URL available');
    setText('estate-detail-status', classification(site));
    setText('estate-detail-products', productUsers(site));
    setText('estate-detail-users', namedAccess(site));
    setText('estate-detail-signals', signals(site));
  }
  function renderTable(sites) {
    const body = $('estate-site-body');
    if (!body) return;
    const q = ($('estate-search')?.value || '').toLowerCase().trim();
    const filter = $('estate-filter')?.value || 'all';
    let visible = sites.slice();
    if (filter !== 'all') visible = visible.filter(site => classification(site) === filter);
    if (q) visible = visible.filter(site => [siteName(site), siteUrl(site), classification(site), signals(site)].join(' ').toLowerCase().includes(q));
    if (!visible.length) {
      body.innerHTML = '<tr><td colspan="6">No estate sites match the current filter.</td></tr>';
      return;
    }
    body.innerHTML = visible.map((site, idx) => row(site, idx)).join('');
    body.querySelectorAll('tr[data-index]').forEach((tr, idx) => {
      tr.addEventListener('click', () => {
        body.querySelectorAll('tr').forEach(r => r.classList.remove('jom-row-selected'));
        tr.classList.add('jom-row-selected');
        renderDetail(visible[idx]);
      });
    });
    renderDetail(visible[0]);
    const first = body.querySelector('tr[data-index]');
    if (first) first.classList.add('jom-row-selected');
  }
  function extractProductSiteCount(productAccess) {
    if (Array.isArray(productAccess.sites)) return productAccess.sites.length;
    if (Array.isArray(productAccess.rows)) return productAccess.rows.length;
    if (productAccess.summary?.site_count !== undefined) return productAccess.summary.site_count;
    if (productAccess.site_count !== undefined) return productAccess.site_count;
    return '--';
  }
  function extractFootprintUsers(footprint) {
    if (Array.isArray(footprint.users)) return footprint.users.length;
    if (Array.isArray(footprint.rows)) return footprint.rows.length;
    return footprint.user_count ?? footprint.total_users ?? '--';
  }
  async function initEstate() {
    if (!$('estate-site-body')) return;
    try {
      const [registry, productAccess, footprint, alerts] = await Promise.all([
        getJson('/registry/sites').catch(() => ({})),
        getJson('/estate/product-access').catch(() => ({})),
        getJson('/users/footprint').catch(() => ({})),
        getJson('/operator/alerts').catch(() => ({})),
      ]);
      const sites = safeArray(registry.sites);
      const monitored = sites.filter(site => classification(site) === 'monitored').length;
      const discovered = sites.length - monitored;
      const productSiteCount = extractProductSiteCount(productAccess);
      const usersAnalysed = extractFootprintUsers(footprint);
      const alertCount = alerts.alert_count ?? alerts.count ?? 0;
      setText('estate-total-sites', sites.length);
      setText('estate-monitored-sites', monitored);
      setText('estate-discovered-sites', discovered);
      setText('estate-product-sites', productSiteCount);
      setText('estate-users-analysed', usersAnalysed);
      setText('estate-alerts', alertCount);
      setText('estate-state', discovered > 0 || alertCount > 0 ? 'Review' : 'Normal');
      setText('estate-growth-sites', sites.length);
      setText('estate-growth-users', usersAnalysed);
      renderTable(sites);
      $('estate-search')?.addEventListener('input', () => renderTable(sites));
      $('estate-filter')?.addEventListener('change', () => renderTable(sites));
      const json = $('estate-json');
      if (json) json.textContent = JSON.stringify({ registry_summary: registry.summary || {}, product_access_summary: productAccess.summary || {}, footprint_summary: footprint.summary || {}, alert_count: alertCount }, null, 2);
    } catch (error) {
      const body = $('estate-site-body');
      if (body) body.innerHTML = `<tr><td colspan="6">Estate failed to load: ${esc(error.message)}</td></tr>`;
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initEstate);
  else initEstate();
})();
/* === Estate Foundation Build v1 END === */

/* === Admin Foundation Build v1 START === */
(() => {
  const $ = (id) => document.getElementById(id);
  const safeArray = (value) => Array.isArray(value) ? value : [];
  const esc = (value) => String(value ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const setText = (id, value) => { const el = $(id); if (el) el.textContent = value === undefined || value === null || value === '' ? '--' : String(value); };
  async function getJson(path) {
    const response = await fetch(path, { cache: 'no-store' });
    if (!response.ok) throw new Error(`${path} returned ${response.status}`);
    return response.json();
  }
  function siteName(site) { return site.site_name || site.site_key || site.key || site.cloud_id || 'Unknown site'; }
  function siteUrl(site) { return site.site_url || site.url || site.cloud_id || ''; }
  function classification(site) { return String(site.classification || site.status || 'discovered').toLowerCase(); }
  function signals(site) {
    const output = [];
    if (site.metrics?.jira_product_user_count !== undefined) output.push(`Product users: ${site.metrics.jira_product_user_count}`);
    if (site.metrics?.named_access_count !== undefined) output.push(`Named direct: ${site.metrics.named_access_count}`);
    if (Array.isArray(site.sources)) output.push(`Sources: ${site.sources.join(', ')}`);
    return output.join(' | ') || 'No signal details available';
  }
  function statusBadge(site) {
    const cls = classification(site);
    return `<span class="jom-status ${cls === 'monitored' ? 'jom-status--monitored' : ''}">${esc(cls)}</span>`;
  }
  function actionCell(site) {
    const url = siteUrl(site);
    const open = url && /^https?:\/\//i.test(url) ? `<a class="jom-pill jom-pill--link" href="${esc(url)}" target="_blank" rel="noopener noreferrer">Open</a>` : '<span class="jom-admin-action-muted">No URL</span>';
    const note = classification(site) === 'monitored' ? '<span class="jom-admin-action-muted">Monitored</span>' : '<span class="jom-admin-action-muted">Review</span>';
    return `<div class="jom-admin-action-stack">${open}${note}</div>`;
  }
  function row(site, idx) {
    return `<tr data-index="${idx}" data-classification="${esc(classification(site))}"><td><strong>${esc(siteName(site))}</strong><br><small>${esc(site.site_key || '')}</small></td><td>${esc(siteUrl(site) || site.cloud_id || 'Unknown')}</td><td>${statusBadge(site)}</td><td>${esc(site.collector_onboarding_status || '')}</td><td>${esc(signals(site))}</td><td>${actionCell(site)}</td></tr>`;
  }
  function renderDiscovery(sites) {
    const body = $('admin-discovery-body');
    if (!body) return;
    const q = ($('admin-discovery-search')?.value || '').toLowerCase().trim();
    const filter = $('admin-discovery-filter')?.value || 'all';
    let visible = sites.slice();
    if (filter !== 'all') visible = visible.filter(site => classification(site) === filter);
    if (q) visible = visible.filter(site => [siteName(site), siteUrl(site), classification(site), signals(site), site.collector_onboarding_status || ''].join(' ').toLowerCase().includes(q));
    if (!visible.length) {
      body.innerHTML = '<tr><td colspan="6">No registry rows match the current filter.</td></tr>';
      return;
    }
    body.innerHTML = visible.map(row).join('');
  }
  function extractAdminUsers(adminTruth, footprint) {
    return adminTruth.user_count ?? adminTruth.users_analysed ?? adminTruth.summary?.user_count ?? footprint.user_count ?? footprint.total_users ?? (Array.isArray(footprint.users) ? footprint.users.length : Array.isArray(footprint.rows) ? footprint.rows.length : '--');
  }
  function namedAccessStatus(adminTruth) {
    return adminTruth.safe_named_access ?? adminTruth.named_access_status ?? adminTruth.summary?.safe_named_access ?? 'Review';
  }
  function runtimeStatus(summary) {
    const raw = summary.runtime_status ?? summary.status ?? summary.summary?.runtime_status;
    if (raw) return raw;
    return /ok|healthy|stable|success/i.test(JSON.stringify(summary)) ? 'OK' : 'Review';
  }
  function sourceState(sourceStatePayload) {
    return sourceStatePayload.status ?? sourceStatePayload.state ?? sourceStatePayload.summary?.status ?? 'Review';
  }
  async function initAdmin() {
    if (!$('admin-discovery-body')) return;
    try {
      const [adminTruth, registry, sourceStatePayload, summary, alerts, footprint] = await Promise.all([
        getJson('/admin/truth').catch(() => ({})),
        getJson('/api/site-registry').catch(() => getJson('/registry/sites').catch(() => ({}))),
        getJson('/api/source-state').catch(() => ({})),
        getJson('/operator/summary').catch(() => ({})),
        getJson('/operator/alerts').catch(() => ({})),
        getJson('/users/footprint').catch(() => ({})),
      ]);
      const sites = safeArray(registry.sites);
      const monitored = sites.filter(site => classification(site) === 'monitored').length;
      const discovered = sites.length - monitored;
      const users = extractAdminUsers(adminTruth, footprint);
      const namedStatus = namedAccessStatus(adminTruth);
      const alertCount = alerts.alert_count ?? alerts.count ?? 0;
      const runtime = runtimeStatus(summary);
      const source = sourceState(sourceStatePayload);
      setText('admin-users-analysed', users);
      setText('admin-named-access', namedStatus);
      setText('admin-total-sites', sites.length);
      setText('admin-monitored-sites', monitored);
      setText('admin-discovered-sites', discovered);
      setText('admin-alerts', alertCount);
      setText('admin-state', discovered > 0 || alertCount > 0 ? 'Review' : 'Normal');
      setText('admin-card-users', users);
      setText('admin-card-named-access', namedStatus);
      setText('admin-card-footprint', Array.isArray(footprint.users) ? `${footprint.users.length} users` : Array.isArray(footprint.rows) ? `${footprint.rows.length} rows` : 'Available');
      setText('admin-runtime-status', runtime);
      setText('admin-source-state', source);
      setText('admin-card-alerts', alertCount);
      setText('admin-contract-truth', Object.keys(adminTruth || {}).length ? 'Connected' : 'Review');
      setText('admin-contract-registry', sites.length ? 'Connected' : 'Review');
      setText('admin-contract-operator', Object.keys(summary || {}).length ? 'Connected' : 'Review');
      renderDiscovery(sites);
      $('admin-discovery-search')?.addEventListener('input', () => renderDiscovery(sites));
      $('admin-discovery-filter')?.addEventListener('change', () => renderDiscovery(sites));
      const json = $('admin-json');
      if (json) json.textContent = JSON.stringify({ admin_truth_summary: adminTruth.summary || {}, registry_summary: registry.summary || {}, source_state: sourceStatePayload.summary || sourceStatePayload, runtime_status: runtime, alert_count: alertCount }, null, 2);
    } catch (error) {
      const body = $('admin-discovery-body');
      if (body) body.innerHTML = `<tr><td colspan="6">Admin failed to load: ${esc(error.message)}</td></tr>`;
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initAdmin);
  else initAdmin();
})();
/* === Admin Foundation Build v1 END === */


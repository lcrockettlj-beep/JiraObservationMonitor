
// --- JOM FRONTEND STATIC TRUTH ELIMINATION v1 START ---
// Frontend truth must come from backend API contracts, not static/data JSON snapshots.
window.JOM_FRONTEND_TRUTH_SOURCE_RECONNECT_V1 = {
  appliedAtUtc: "2026-07-23T09:25:55Z",
  rule: "Frontend must not read static/data/*.json as truth. Use backend API contracts only.",
  contracts: {
    productAccess: "/estate/product-access",
    adminTruth: "/admin/truth",
    userFootprint: "/users/footprint",
    siteRegistry: "/registry/sites",
    sourceState: "/api/source-state"
  }
};

function unwrapJomBackendContractV1(payload) {
  if (!payload || typeof payload !== "object") return payload;
  if (payload.schema === "jom-backend-route-contract-v1" && payload.data && typeof payload.data === "object") {
    return payload.data;
  }
  return payload;
}

function unwrapJomBackendContractEnvelopeV1(payload) {
  if (!payload || typeof payload !== "object") return payload;
  const copy = Array.isArray(payload) ? payload.slice() : { ...payload };
  for (const key of Object.keys(copy)) {
    copy[key] = unwrapJomBackendContractV1(copy[key]);
  }
  return unwrapJomBackendContractV1(copy);
}
// --- JOM FRONTEND STATIC TRUTH ELIMINATION v1 END ---

/* JOM Site Workspace Source Merge v1 */
(function(){
  'use strict';

  const siteKey = document.body.getAttribute('data-site-key') || '';
  const endpoints = {
    registry: '/registry/sites',
    surface: '/operator/surface',
    productAccess: '/estate/product-access',
    footprint: '/users/footprint',
    summary: '/operator/summary',
    alerts: '/operator/alerts',
    sourceState: '/api/source-state',
    billingSeats: '/estate/product-access',
    estateProductAccess: '/estate/product-access',
    estateAccessTruth: '/admin/truth',
    adminNamedAccess: '/users/footprint',
    namedAccessTruth: '/users/footprint'
  };

  const $ = selector => document.querySelector(selector);
  const setText = (selector, value) => {
    const el = $(selector);
    if (!el) return;
    el.textContent = value === undefined || value === null || value === '' ? 'Unavailable' : String(value);
  };

  function normalise(value){
    return String(value || '')
      .toLowerCase()
      .replace(/^https?:\/\//,'')
      .replace(/\.atlassian\.net.*$/,'')
      .replace(/\/$/,'')
      .split('/')[0]
      .trim();
  }

  function escapeHtml(value){
    return String(value ?? '').replace(/[&<>"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[ch]));
  }

  async function getJson(url){
    try {
      const res = await fetch(url, {cache:'no-store'});
      if(!res.ok) return null;
      const payload = await res.json();
    return unwrapJomBackendContractEnvelopeV1(payload);
    } catch(_error) {
      return null;
    }
  }

  function readAny(obj, keys, fallback){
    if(!obj) return fallback;
    for(const key of keys){
      if(obj[key] !== undefined && obj[key] !== null && obj[key] !== '') return obj[key];
      if(obj.metrics && obj.metrics[key] !== undefined && obj.metrics[key] !== null && obj.metrics[key] !== '') return obj.metrics[key];
      if(obj.summary && obj.summary[key] !== undefined && obj.summary[key] !== null && obj.summary[key] !== '') return obj.summary[key];
      if(obj.billing && obj.billing[key] !== undefined && obj.billing[key] !== null && obj.billing[key] !== '') return obj.billing[key];
    }
    return fallback;
  }

  function siteUrl(site){ return readAny(site, ['site_url','url','base_url','cloud_url'], 'Unavailable'); }
  function siteName(site){ return readAny(site, ['site_name','name','site_key','key','slug','url','site_url'], siteKey); }
  function siteStatus(site){ return readAny(site, ['classification','status','state','monitoring_status','discovery_status'], 'Unavailable'); }
  function isMonitored(site){
    const raw = String(siteStatus(site)).toLowerCase();
    return raw === 'monitored' || raw.includes('monitored') || (site && (site.monitored === true || site.is_monitored === true));
  }

  function findRegistrySite(registry){
    const sites = Array.isArray(registry && registry.sites) ? registry.sites : [];
    const target = normalise(siteKey);
    return sites.find(s => normalise(readAny(s, ['site_key','key','slug','name','site_name','url','site_url'], '')) === target || normalise(siteUrl(s)) === target)
      || sites.find(s => JSON.stringify(s).toLowerCase().includes(target));
  }

  function containsSite(row){
    const target = normalise(siteKey);
    return row && JSON.stringify(row).toLowerCase().includes(target);
  }

  function walkRows(obj, rows=[]){
    if(!obj) return rows;
    if(Array.isArray(obj)){
      obj.forEach(x => walkRows(x, rows));
      return rows;
    }
    if(typeof obj === 'object'){
      if(containsSite(obj)) rows.push(obj);
      Object.keys(obj).forEach(k => {
        const v = obj[k];
        if(v && typeof v === 'object') walkRows(v, rows);
      });
    }
    return rows;
  }

  function flattenProductRows(productAccess){
    if(!productAccess) return [];
    if(Array.isArray(productAccess.rows)) return productAccess.rows;
    if(Array.isArray(productAccess.sites)) return productAccess.sites;
    if(Array.isArray(productAccess.product_access)) return productAccess.product_access;
    return walkRows(productAccess, []);
  }

  function findProductSite(productAccess){
    const rows = flattenProductRows(productAccess);
    const target = normalise(siteKey);
    return rows.find(s => normalise(readAny(s, ['site_key','key','site','slug','name','site_name','url','site_url'], '')) === target)
      || rows.find(s => JSON.stringify(s).toLowerCase().includes(target));
  }

  function parseUsed(value){
    if(value === undefined || value === null || value === '') return null;
    if(typeof value === 'number' && Number.isFinite(value)) return value;
    const s = String(value).trim();
    let m = s.match(/(\d+)\s*\/\s*(\d+)/);
    if(m) return Number(m[1]);
    m = s.match(/\b(\d+)\b/);
    return m ? Number(m[1]) : null;
  }

  function parseCapacity(value){
    if(value === undefined || value === null || value === '') return null;
    const s = String(value).trim();
    const m = s.match(/(\d+)\s*\/\s*(\d+)/);
    return m ? Number(m[2]) : null;
  }

  function productName(row){
    return readAny(row, ['product','product_name','app','app_name','application','subscription_name','title','name','key'], 'Atlassian product');
  }

  function planName(row){ return readAny(row, ['plan','tier','edition','billing_plan','license_plan'], 'Unavailable'); }
  function sourceName(row, fallback){ return readAny(row, ['source','source_file','data_source'], fallback || 'source'); }

  function usersRaw(row){
    return readAny(row, ['users','user_count','used','used_users','licensed_users','product_users','jira_users','confluence_users','seats_used','active_users','count'], undefined);
  }

  function extractProductRows(payload, source){
    const rows = [];
    walkRows(payload, []).forEach(row => {
      if(!containsSite(row)) return;
      const raw = usersRaw(row);
      const used = parseUsed(raw);
      const cap = parseCapacity(raw) || parseUsed(readAny(row, ['capacity','limit','seats','seat_limit','licensed','max_users'], undefined));
      const name = productName(row);
      const plan = planName(row);
      if(name || used !== null || plan !== 'Unavailable'){
        rows.push({
          product: name,
          users: used,
          capacity: cap,
          users_display: used !== null ? (cap ? `${used} / ${cap}` : String(used)) : (raw || 'Unavailable'),
          plan: plan,
          source: sourceName(row, source),
          raw: row
        });
      }
    });
    return rows;
  }

  function dedupeRows(rows){
    const seen = new Set();
    const out = [];
    rows.forEach(row => {
      const key = [normalise(row.product), row.users_display, normalise(row.plan)].join('|');
      if(seen.has(key)) return;
      seen.add(key);
      out.push(row);
    });
    return out;
  }

  function productCount(regSite, productSite, rows){
    if(rows.length) return String(rows.length);
    const explicit = readAny(productSite, ['product_count','products_count'], readAny(regSite, ['product_count','products_count'], undefined));
    if(explicit !== undefined) return explicit;
    if(productSite && Array.isArray(productSite.products)) return productSite.products.length;
    if(productSite && Array.isArray(productSite.roles)) return productSite.roles.length;
    return productSite || regSite ? 'Available' : 'Unavailable';
  }

  function primaryProductUsers(regSite, productSite, rows){
    const jira = rows.find(r => /\bjira\b/i.test(r.product) && r.users !== null);
    const conf = rows.find(r => /confluence/i.test(r.product) && r.users !== null);
    if(jira && conf) return `Jira ${jira.users}; Confluence ${conf.users}`;
    if(jira) return String(jira.users);
    if(conf) return String(conf.users);
    const numeric = rows.filter(r => r.users !== null).map(r => r.users);
    if(numeric.length) return String(Math.max(...numeric));
    const fallback = readAny(productSite, ['jira_product_user_count','product_users','user_count','users','total_users'], readAny(regSite, ['jira_product_user_count','product_users','user_count','users','total_users'], null));
    return fallback !== null ? fallback : 'Unavailable';
  }

  function accessCount(regSite, productSite, accessPayloads){
    const direct = readAny(productSite, ['named_access_count','direct_access_count','access_count','assignment_count','total_product_access_assignments'], readAny(regSite, ['named_access_count','direct_access_count','access_count','assignment_count'], null));
    if(direct !== null && direct !== undefined) return direct;
    const values = [];
    accessPayloads.forEach(payload => {
      walkRows(payload, []).forEach(row => {
        if(!containsSite(row)) return;
        const txt = JSON.stringify(row).toLowerCase();
        if(txt.includes('named') || txt.includes('access') || txt.includes('assignment') || txt.includes('direct')){
          const n = parseUsed(readAny(row, ['named_access_count','direct_access_count','access_count','assignment_count','total_product_access_assignments','count','users','user_count'], undefined));
          if(n !== null) values.push(n);
        }
      });
    });
    return values.length ? Math.max(...values) : 'Unavailable';
  }

  function sourceList(regSite, productSite, rows){
    const values = [];
    if(regSite && Array.isArray(regSite.sources)) values.push(...regSite.sources);
    if(productSite && Array.isArray(productSite.sources)) values.push(...productSite.sources);
    rows.forEach(row => row.source && values.push(row.source));
    if(!values.length) values.push('registry');
    return Array.from(new Set(values.filter(Boolean)));
  }

  function renderProductAccess(rows, hasProductSite){
    const body = $('#site-product-access-body');
    if(!body) return;
    body.innerHTML = '';
    if(rows.length){
      rows.forEach(row => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${escapeHtml(row.product)}</td><td>${escapeHtml(row.users_display)}</td><td>${escapeHtml(row.plan)}</td><td><span class="site-badge site-badge--ok">${escapeHtml(row.source)}</span></td>`;
        body.appendChild(tr);
      });
      return;
    }
    body.innerHTML = `<tr><td colspan="4"><strong>No source-backed product rows currently available.</strong><br>${hasProductSite ? 'Product-access summary exists, but no product rows were exposed for this site.' : 'The site exists in the registry, but billing/product-access rows were not found in the current local data files.'}</td></tr>`;
  }

  function renderSignals(regSite, productSite, rows, alerts, sourceState){
    const list = $('#site-signal-list');
    if(!list) return;
    const signals = [];
    signals.push({state: regSite ? 'ok' : 'review', text: regSite ? 'Registry entry found for this site.' : 'No exact registry entry found; using route key only.'});
    signals.push({state: (productSite || rows.length) ? 'ok' : 'review', text: (productSite || rows.length) ? 'Product/access source data is available for this site.' : 'No product/access source rows were found for this site.'});
    signals.push({state: isMonitored(regSite) ? 'ok' : 'review', text: isMonitored(regSite) ? 'Site is in monitored operational scope.' : 'Site may be discovered or awaiting review.'});
    const alertCount = Number(readAny(alerts, ['alert_count','count'], 0));
    signals.push({state: alertCount > 0 ? 'review' : 'ok', text: alertCount > 0 ? `${alertCount} active operator alert signal(s) exist at estate level.` : 'No active operator alert count reported at estate level.'});
    const source = readAny(sourceState, ['status','state'], null);
    if(source) signals.push({state:'ok', text:'Source state: '+source+'.'});
    list.innerHTML = signals.map(s => `<li class="site-signal-card site-signal-card--${s.state === 'ok' ? 'ok' : 'review'}"><span class="site-signal-icon">${s.state === 'ok' ? 'OK' : '!'}</span>${escapeHtml(s.text)}</li>`).join('');
    list.classList.add('site-signal-cards');
  }

  function renderSummary(productUsers, accessRecords, sources){
    const summary = $('#site-users-summary');
    if(!summary) return;
    summary.innerHTML = ''+
      `<span class="site-user-summary-item">Product users: ${escapeHtml(productUsers)}</span>`+
      `<span class="site-user-summary-item">Access records: ${escapeHtml(accessRecords)}</span>`+
      `<span class="site-user-summary-item">Sources: ${escapeHtml(sources.join(', '))}</span>`;
    summary.classList.add('site-user-summary-grid');
  }

  function applyBadge(selector){
    const el = $(selector);
    if(!el) return;
    const val = String(el.textContent || '').trim();
    const v = val.toLowerCase();
    let cls = 'site-badge';
    if(v.includes('monitored') || v.includes('normal') || v.includes('ok') || v.includes('yes')) cls += ' site-badge--ok';
    else if(v.includes('discover') || v.includes('review') || v.includes('unavailable') || v.includes('pending')) cls += ' site-badge--review';
    el.className = cls;
    el.textContent = val.toUpperCase();
  }

  function removeOldNoise(){
    document.querySelectorAll('.jom-layout-breadcrumb, .jom-readiness-strip, .jom-operational-readiness, [data-jom-readiness], [data-jom-operational-readiness]').forEach(el => el.remove());
  }

  function renderDiagnostics(payload){
    setText('#site-json-diagnostics', JSON.stringify(payload, null, 2));
    const summary = document.querySelector('.site-diagnostics summary');
    if(summary) summary.textContent = 'Developer diagnostics';
  }

  async function init(){
    removeOldNoise();
    try{
      const [registry, surface, productAccess, footprint, summary, alerts, sourceState, billingSeats, estateProductAccess, estateAccessTruth, adminNamedAccess, namedAccessTruth] = await Promise.all([
        getJson(endpoints.registry), getJson(endpoints.surface), getJson(endpoints.productAccess), getJson(endpoints.footprint), getJson(endpoints.summary), getJson(endpoints.alerts), getJson(endpoints.sourceState),
        getJson(endpoints.billingSeats), getJson(endpoints.estateProductAccess), getJson(endpoints.estateAccessTruth), getJson(endpoints.adminNamedAccess), getJson(endpoints.namedAccessTruth)
      ]);

      const regSite = findRegistrySite(registry);
      const productSite = findProductSite(productAccess);
      const productRows = dedupeRows([]
        .concat(extractProductRows(billingSeats, 'billing_seats'))
        .concat(extractProductRows(estateProductAccess, 'estate_product_access'))
        .concat(extractProductRows(productAccess, 'estate_product_access_api'))
      );
      const productUsers = primaryProductUsers(regSite, productSite, productRows);
      const accessRecords = accessCount(regSite, productSite, [estateAccessTruth, adminNamedAccess, namedAccessTruth]);
      const products = productCount(regSite, productSite, productRows);
      const sources = sourceList(regSite, productSite, productRows);
      const title = siteName(regSite || productSite || {site_key: siteKey});

      document.title = 'JOM - ' + title;
      setText('#site-title', title);
      setText('#site-title-breadcrumb', title);
      setText('#site-status-pill', siteStatus(regSite));
      setText('[data-site-field="key"]', siteKey);
      setText('[data-site-field="url"]', siteUrl(regSite || productSite));
      setText('[data-site-field="monitored"]', isMonitored(regSite) ? 'Yes' : 'Review');
      setText('[data-site-field="discovery"]', siteStatus(regSite));
      setText('[data-site-field="products"]', products);
      setText('[data-site-field="users"]', productUsers);
      setText('[data-site-field="assignments"]', accessRecords);
      setText('[data-site-field="registry-state"]', siteStatus(regSite));
      setText('[data-site-field="risk"]', isMonitored(regSite) ? 'Normal' : 'Review');
      setText('[data-site-field="last-seen"]', readAny(registry, ['generated_at_utc','generated_at','last_refresh'], readAny(surface, ['generated_at_utc','generated_at'], 'Unavailable')));

      renderSignals(regSite, productSite, productRows, alerts, sourceState);
      renderProductAccess(productRows, !!productSite);
      renderSummary(productUsers, accessRecords, sources);
      applyBadge('#site-status-pill');
      applyBadge('[data-site-field="monitored"]');
      applyBadge('[data-site-field="registry-state"]');
      applyBadge('[data-site-field="risk"]');
      renderDiagnostics({
        route_site_key: siteKey,
        resolved_site_name: title,
        registry_match: regSite || null,
        product_access_match: productSite || null,
        product_rows: productRows,
        derived: {products, product_users: productUsers, access_records: accessRecords, monitored: isMonitored(regSite), status: siteStatus(regSite), sources},
        source_state: sourceState && (sourceState.summary || sourceState),
        footprint_summary: footprint && (footprint.summary || {user_count: footprint.user_count, total_users: footprint.total_users}),
        operator_summary: summary && (summary.summary || summary.runtime || summary),
        alert_summary: alerts && (alerts.summary || alerts)
      });
    } catch(e){
      setText('#site-title', siteKey || 'Site Workspace');
      setText('#site-status-pill', 'Review');
      setText('#site-json-diagnostics', 'Failed to load site workspace data: ' + e.message);
    }
  }

  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();

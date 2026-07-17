/* JOM Site Workspace v1 */
(function(){
  const siteKey = document.body.getAttribute('data-site-key') || '';
  const endpoints = {
    registry: '/registry/sites',
    surface: '/operator/surface',
    productAccess: '/estate/product-access',
    footprint: '/users/footprint'
  };
  const $ = (sel) => document.querySelector(sel);
  const setText = (sel, value) => { const el = $(sel); if(el) el.textContent = value ?? 'Unavailable'; };
  async function getJson(url){ const r = await fetch(url,{cache:'no-store'}); if(!r.ok) throw new Error(url+' '+r.status); return r.json(); }
  function normaliseSiteKey(value){ return String(value||'').toLowerCase().replace(/^https?:\/\//,'').replace(/\.atlassian\.net.*$/,'').replace(/\/$/,''); }
  function findRegistrySite(registry){
    const sites = Array.isArray(registry.sites) ? registry.sites : [];
    const target = normaliseSiteKey(siteKey);
    return sites.find(s => normaliseSiteKey(s.key||s.site_key||s.slug||s.name||s.url) === target || normaliseSiteKey(s.url) === target) || sites.find(s => JSON.stringify(s).toLowerCase().includes(target));
  }
  function findProductSite(productAccess){
    const sites = Array.isArray(productAccess.sites) ? productAccess.sites : [];
    const target = normaliseSiteKey(siteKey);
    return sites.find(s => normaliseSiteKey(s.key||s.site_key||s.site||s.name||s.url) === target || JSON.stringify(s).toLowerCase().includes(target));
  }
  function renderProductAccess(site){
    const body = $('#site-product-access-body'); if(!body) return;
    body.innerHTML = '';
    const roles = site && site.roles ? site.roles : [];
    if(Array.isArray(roles) && roles.length){
      roles.forEach(role => {
        const tr = document.createElement('tr');
        tr.innerHTML = '<td>'+(role.product||role.key||'Product')+'</td><td>'+(role.user_count??role.count??'Unavailable')+'</td><td>'+(role.role||role.name||'Access')+'</td><td>Source-backed</td>';
        body.appendChild(tr);
      });
      return;
    }
    const summary = site && site.summary ? site.summary : site;
    if(summary){
      const tr = document.createElement('tr');
      tr.innerHTML = '<td>Atlassian products</td><td>'+(summary.user_count??summary.users??summary.total_users??'Unavailable')+'</td><td>'+(summary.role_count??'Unavailable')+'</td><td>Available</td>';
      body.appendChild(tr);
    } else {
      body.innerHTML = '<tr><td colspan="4">No product-access rows available for this site.</td></tr>';
    }
  }
  function renderSignals(regSite, productSite){
    const list = $('#site-signal-list'); if(!list) return;
    const signals = [];
    if(regSite) signals.push('Registry entry found for this site.'); else signals.push('No exact registry entry found; using route key only.');
    if(productSite) signals.push('Product-access data available for this site.'); else signals.push('No product-access match found for this site.');
    const state = regSite && (regSite.status || regSite.state || regSite.monitoring_status);
    if(state) signals.push('Registry state: '+ state);
    list.innerHTML = signals.map(s => '<li>'+s+'</li>').join('');
  }
  async function init(){
    try{
      const [registry, surface, productAccess, footprint] = await Promise.all([getJson(endpoints.registry), getJson(endpoints.surface), getJson(endpoints.productAccess), getJson(endpoints.footprint)]);
      const regSite = findRegistrySite(registry);
      const productSite = findProductSite(productAccess);
      const title = (regSite && (regSite.name || regSite.site_name || regSite.key || regSite.url)) || siteKey;
      document.title = 'JOM - ' + title;
      setText('#site-title', title);
      setText('#site-title-breadcrumb', title);
      setText('#site-status-pill', (regSite && (regSite.status || regSite.state || regSite.monitoring_status)) || 'Review');
      setText('[data-site-field="key"]', siteKey);
      setText('[data-site-field="url"]', (regSite && regSite.url) || 'Unavailable');
      setText('[data-site-field="monitored"]', (regSite && (regSite.monitored !== undefined ? regSite.monitored : regSite.is_monitored)) ? 'Yes' : 'Review');
      setText('[data-site-field="discovery"]', (regSite && (regSite.discovery_status || regSite.state || regSite.status)) || 'Unavailable');
      setText('[data-site-field="products"]', productSite ? String((productSite.products && productSite.products.length) || (productSite.roles && productSite.roles.length) || 'Available') : 'Unavailable');
      setText('[data-site-field="users"]', productSite ? String(productSite.user_count ?? productSite.users ?? productSite.total_users ?? 'Available') : 'Unavailable');
      setText('[data-site-field="assignments"]', productSite ? String(productSite.assignment_count ?? productSite.total_product_access_assignments ?? 'Available') : 'Unavailable');
      setText('[data-site-field="registry-state"]', (regSite && (regSite.status || regSite.state || regSite.monitoring_status)) || 'Unavailable');
      setText('[data-site-field="risk"]', (surface && surface.posture && surface.posture.state) || 'Source-backed');
      setText('[data-site-field="last-seen"]', (registry && registry.generated_at_utc) || (surface && surface.generated_at_utc) || 'Unavailable');
      setText('#site-users-summary', 'User footprint summary: ' + JSON.stringify((footprint && footprint.summary) || {}, null, 0));
      renderSignals(regSite, productSite);
      renderProductAccess(productSite);
      setText('#site-json-diagnostics', JSON.stringify({route_site_key:siteKey, registry_site:regSite || null, product_access_site:productSite || null}, null, 2));
    } catch(e){
      setText('#site-title', siteKey || 'Site Workspace');
      setText('#site-status-pill', 'Review');
      setText('#site-json-diagnostics', 'Failed to load site workspace data: ' + e.message);
    }
  }
  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
/* === Site Workspace Data Enrichment v1 START === */
(function(){
  const siteKey = document.body.getAttribute('data-site-key') || '';
  const endpoints = {
    registry: '/registry/sites',
    surface: '/operator/surface',
    productAccess: '/estate/product-access',
    footprint: '/users/footprint',
    summary: '/operator/summary',
    alerts: '/operator/alerts',
    sourceState: '/api/source-state'
  };
  const $ = (sel) => document.querySelector(sel);
  const setText = (sel, value) => { const el = $(sel); if(el) el.textContent = value === undefined || value === null || value === '' ? 'Unavailable' : String(value); };
  const number = (value, fallback) => Number.isFinite(Number(value)) ? Number(value) : fallback;
  async function getJson(url){ const r = await fetch(url,{cache:'no-store'}); if(!r.ok) throw new Error(url+' '+r.status); return r.json(); }
  function normaliseSiteKey(value){ return String(value||'').toLowerCase().replace(/^https?:\/\//,'').replace(/\.atlassian\.net.*$/,'').replace(/\/$/,'').split('/')[0]; }
  function readAny(obj, keys, fallback){
    if(!obj) return fallback;
    for(const key of keys){
      if(obj[key] !== undefined && obj[key] !== null && obj[key] !== '') return obj[key];
      if(obj.metrics && obj.metrics[key] !== undefined && obj.metrics[key] !== null && obj.metrics[key] !== '') return obj.metrics[key];
      if(obj.summary && obj.summary[key] !== undefined && obj.summary[key] !== null && obj.summary[key] !== '') return obj.summary[key];
    }
    return fallback;
  }
  function siteName(site){ return readAny(site, ['site_name','name','site_key','key','slug','url','site_url'], siteKey); }
  function siteUrl(site){ return readAny(site, ['site_url','url','base_url','cloud_url'], 'Unavailable'); }
  function siteStatus(site){ return readAny(site, ['classification','status','state','monitoring_status','discovery_status'], 'Unavailable'); }
  function isMonitored(site){
    const raw = String(siteStatus(site)).toLowerCase();
    if(raw === 'monitored') return true;
    if(site && (site.monitored === true || site.is_monitored === true)) return true;
    return false;
  }
  function findRegistrySite(registry){
    const sites = Array.isArray(registry.sites) ? registry.sites : [];
    const target = normaliseSiteKey(siteKey);
    return sites.find(s => normaliseSiteKey(readAny(s,['site_key','key','slug','name','site_name','url','site_url'],'')) === target || normaliseSiteKey(siteUrl(s)) === target)
      || sites.find(s => JSON.stringify(s).toLowerCase().includes(target));
  }
  function flattenProductRows(productAccess){
    if(!productAccess) return [];
    if(Array.isArray(productAccess.rows)) return productAccess.rows;
    if(Array.isArray(productAccess.sites)) return productAccess.sites;
    if(Array.isArray(productAccess.product_access)) return productAccess.product_access;
    return [];
  }
  function findProductSite(productAccess){
    const rows = flattenProductRows(productAccess);
    const target = normaliseSiteKey(siteKey);
    return rows.find(s => normaliseSiteKey(readAny(s,['site_key','key','site','slug','name','site_name','url','site_url'],'')) === target || JSON.stringify(s).toLowerCase().includes(target));
  }
  function productUserCount(regSite, productSite){
    return readAny(productSite, ['jira_product_user_count','product_users','user_count','users','total_users'], readAny(regSite, ['jira_product_user_count','product_users','user_count','users','total_users'], 'Unavailable'));
  }
  function namedAccessCount(regSite, productSite){
    return readAny(productSite, ['named_access_count','named_direct','named_users','access_count','assignment_count','total_product_access_assignments'], readAny(regSite, ['named_access_count','named_direct','named_users','access_count'], 'Unavailable'));
  }
  function productCount(regSite, productSite){
    const explicit = readAny(productSite, ['product_count','products_count'], readAny(regSite, ['product_count','products_count'], undefined));
    if(explicit !== undefined) return explicit;
    if(productSite && Array.isArray(productSite.products)) return productSite.products.length;
    if(productSite && Array.isArray(productSite.roles)) return productSite.roles.length;
    return productSite || regSite ? 'Available' : 'Unavailable';
  }
  function sourceList(regSite, productSite){
    const values = [];
    if(regSite && Array.isArray(regSite.sources)) values.push(...regSite.sources);
    if(productSite && Array.isArray(productSite.sources)) values.push(...productSite.sources);
    if(!values.length) values.push('registry');
    if(productSite) values.push('product_access');
    return Array.from(new Set(values.filter(Boolean)));
  }
  function renderProductAccess(regSite, productSite){
    const body = $('#site-product-access-body'); if(!body) return;
    const users = productUserCount(regSite, productSite);
    const assignments = namedAccessCount(regSite, productSite);
    const products = productCount(regSite, productSite);
    body.innerHTML = '';
    if(productSite && Array.isArray(productSite.roles) && productSite.roles.length){
      productSite.roles.forEach(role => {
        const tr = document.createElement('tr');
        tr.innerHTML = '<td>'+(role.product||role.key||'Atlassian product')+'</td><td>'+(role.user_count??role.count??users)+'</td><td>'+(role.role||role.name||assignments)+'</td><td>Source-backed</td>';
        body.appendChild(tr);
      });
      return;
    }
    const tr = document.createElement('tr');
    tr.innerHTML = '<td>Atlassian products</td><td>'+users+'</td><td>'+assignments+'</td><td>'+(productSite ? 'Source-backed' : 'Registry only')+'</td>';
    body.appendChild(tr);
  }
  function renderSignals(regSite, productSite, summary, alerts, sourceState){
    const list = $('#site-signal-list'); if(!list) return;
    const signals = [];
    signals.push(regSite ? 'Registry entry found for this site.' : 'No exact registry entry found; using route key only.');
    signals.push(productSite ? 'Product-access data is available for this site.' : 'No product-access match found for this site.');
    signals.push(isMonitored(regSite) ? 'Site is in monitored operational scope.' : 'Site may be discovered or awaiting review.');
    const activeAlerts = readAny(alerts, ['alert_count','count'], 0);
    signals.push(Number(activeAlerts) > 0 ? activeAlerts + ' active operator alert signal(s) exist at estate level.' : 'No active operator alert count reported at estate level.');
    const srcState = readAny(sourceState, ['status','state'], 'Review');
    signals.push('Source state: ' + srcState + '.');
    list.innerHTML = signals.map(s => '<li>'+s+'</li>').join('');
  }
  function renderDiagnostics(payload){
    setText('#site-json-diagnostics', JSON.stringify(payload, null, 2));
  }
  async function init(){
    try{
      const [registry, surface, productAccess, footprint, summary, alerts, sourceState] = await Promise.all([
        getJson(endpoints.registry), getJson(endpoints.surface), getJson(endpoints.productAccess), getJson(endpoints.footprint),
        getJson(endpoints.summary), getJson(endpoints.alerts), getJson(endpoints.sourceState)
      ]);
      const regSite = findRegistrySite(registry);
      const productSite = findProductSite(productAccess);
      const title = siteName(regSite || productSite || {site_key: siteKey});
      const users = productUserCount(regSite, productSite);
      const assignments = namedAccessCount(regSite, productSite);
      const products = productCount(regSite, productSite);
      const sources = sourceList(regSite, productSite);
      document.title = 'JOM - ' + title;
      setText('#site-title', title);
      setText('#site-title-breadcrumb', title);
      setText('#site-status-pill', siteStatus(regSite));
      setText('[data-site-field="key"]', siteKey);
      setText('[data-site-field="url"]', siteUrl(regSite || productSite));
      setText('[data-site-field="monitored"]', isMonitored(regSite) ? 'Yes' : 'Review');
      setText('[data-site-field="discovery"]', siteStatus(regSite));
      setText('[data-site-field="products"]', products);
      setText('[data-site-field="users"]', users);
      setText('[data-site-field="assignments"]', assignments);
      setText('[data-site-field="registry-state"]', siteStatus(regSite));
      setText('[data-site-field="risk"]', isMonitored(regSite) ? 'Normal' : 'Review');
      setText('[data-site-field="last-seen"]', readAny(registry, ['generated_at_utc','generated_at','last_refresh'], readAny(surface, ['generated_at_utc','generated_at'], 'Unavailable')));
      setText('#site-users-summary', 'Product users: ' + users + ' | Named direct: ' + assignments + ' | Sources: ' + sources.join(', '));
      renderSignals(regSite, productSite, summary, alerts, sourceState);
      renderProductAccess(regSite, productSite);
      renderDiagnostics({
        route_site_key: siteKey,
        resolved_site_name: title,
        registry_match: regSite || null,
        product_access_match: productSite || null,
        derived: {products, users, assignments, monitored: isMonitored(regSite), status: siteStatus(regSite), sources},
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
  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
/* === Site Workspace Data Enrichment v1 END === */
/* === Site Workspace UX Freeze-Safe Closeout v1 START === */
(function(){
  function text(el){ return (el && el.textContent ? el.textContent : '').trim(); }
  function normalise(value){ return String(value || '').trim().toLowerCase(); }
  function isLoading(value){ return !value || value === 'Loading...' || value === 'LOADING...'; }
  function badgeClass(value){
    const v = normalise(value);
    if(v.includes('monitored') || v.includes('normal') || v.includes('ok') || v.includes('yes')) return 'site-badge site-badge--ok';
    if(v.includes('discover') || v.includes('review') || v.includes('unavailable') || v.includes('pending')) return 'site-badge site-badge--review';
    return 'site-badge';
  }
  function applyBadge(selector){
    const el = document.querySelector(selector);
    if(!el) return false;
    const val = text(el);
    if(isLoading(val)) return false;
    if(el.dataset.uxBadgeValue === val) return true;
    el.textContent = val.toUpperCase();
    el.className = badgeClass(val);
    el.dataset.uxBadgeValue = val;
    return true;
  }
  function convertSignals(){
    const list = document.getElementById('site-signal-list');
    if(!list) return false;
    const current = text(list);
    if(isLoading(current) || current.includes('Loading signals')) return false;
    list.classList.add('site-signal-cards');
    Array.from(list.querySelectorAll('li')).forEach(item => {
      if(item.dataset.uxSignalClosed === 'true') return;
      const content = text(item);
      const lowered = normalise(content);
      item.classList.add('site-signal-card');
      if(lowered.includes('no exact') || lowered.includes('no product') || lowered.includes('awaiting') || lowered.includes('review')) item.classList.add('site-signal-card--review');
      else item.classList.add('site-signal-card--ok');
      const icon = document.createElement('span');
      icon.className = 'site-signal-icon';
      icon.textContent = item.classList.contains('site-signal-card--ok') ? 'OK' : '!';
      item.insertBefore(icon, item.firstChild);
      item.dataset.uxSignalClosed = 'true';
    });
    return true;
  }
  function improveEmptyStates(){
    document.querySelectorAll('[data-site-field]').forEach(el => {
      const value = text(el);
      if(value === 'Unavailable') el.classList.add('site-empty-value');
    });
    const body = document.getElementById('site-product-access-body');
    if(body && !body.dataset.uxEmptyChecked && /Unavailable|No product-access/i.test(body.innerText)){
      body.innerHTML = '<tr><td colspan="4"><strong>No source-backed product access currently available.</strong><br><span class="site-muted">This site exists in the registry but has not yet produced product-access data.</span></td></tr>';
      body.dataset.uxEmptyChecked = 'true';
    }
  }
  function improveUserSummary(){
    const summary = document.getElementById('site-users-summary');
    if(!summary || summary.dataset.uxClosedOut === 'true') return false;
    const raw = text(summary);
    if(isLoading(raw)) return false;
    const parts = raw.split('|').map(x => x.trim()).filter(Boolean);
    if(parts.length){
      summary.innerHTML = '<span>' + parts.join('</span><span>') + '</span>';
      summary.classList.add('site-user-summary-grid');
      summary.dataset.uxClosedOut = 'true';
      return true;
    }
    return false;
  }
  function renameDiagnostics(){
    const summary = document.querySelector('.site-diagnostics summary');
    if(summary) summary.textContent = 'Developer diagnostics';
  }
  function runCloseout(){
    applyBadge('#site-status-pill');
    applyBadge('[data-site-field="monitored"]');
    applyBadge('[data-site-field="registry-state"]');
    applyBadge('[data-site-field="risk"]');
    convertSignals();
    improveEmptyStates();
    improveUserSummary();
    renameDiagnostics();
  }
  function scheduleCloseout(){
    [250, 750, 1500, 3000, 5000, 8000].forEach(delay => window.setTimeout(runCloseout, delay));
  }
  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', scheduleCloseout);
  else scheduleCloseout();
})();
/* === Site Workspace UX Freeze-Safe Closeout v1 END === */

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

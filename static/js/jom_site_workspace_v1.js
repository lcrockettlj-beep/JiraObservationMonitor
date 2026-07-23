// --- JOM SITE WORKSPACE UI DISPLAY ALIGNMENT v1 START ---
// Site Workspace must render backend API contracts only. No static/data truth reads.
(function(){
  'use strict';

  const siteKey = document.body.getAttribute('data-site-key') || '';
  const endpoints = {
    registry: '/registry/sites',
    productAccess: '/estate/product-access',
    adminTruth: '/admin/truth',
    footprint: '/users/footprint',
    sourceState: '/api/source-state',
    oauthCoverage: '/api/oauth/coverage/' + encodeURIComponent(siteKey),
    operatorSurface: '/operator/surface',
    operatorSummary: '/operator/summary',
    operatorAlerts: '/operator/alerts'
  };

  const $ = selector => document.querySelector(selector);
  const setText = (selector, value) => {
    const el = $(selector);
    if (!el) return;
    el.textContent = value === undefined || value === null || value === '' ? 'Unavailable' : String(value);
  };

  function unwrapContract(payload){
    if (!payload || typeof payload !== 'object') return payload;
    if (payload.schema === 'jom-backend-route-contract-v1' && payload.data && typeof payload.data === 'object') return payload.data;
    return payload;
  }

  function unwrapEnvelope(payload){
    payload = unwrapContract(payload);
    if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return payload;
    const out = {...payload};
    Object.keys(out).forEach(key => { out[key] = unwrapContract(out[key]); });
    return unwrapContract(out);
  }

  async function getJson(url){
    try {
      const res = await fetch(url, {cache: 'no-store'});
      if (!res.ok) return null;
      return unwrapEnvelope(await res.json());
    } catch (_error){
      return null;
    }
  }

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
    return String(value ?? '').replace(/[&<>\"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[ch]));
  }

  function readAny(obj, keys, fallback){
    if (!obj || typeof obj !== 'object') return fallback;
    for (const key of keys){
      if (obj[key] !== undefined && obj[key] !== null && obj[key] !== '') return obj[key];
      if (obj.metrics && obj.metrics[key] !== undefined && obj.metrics[key] !== null && obj.metrics[key] !== '') return obj.metrics[key];
      if (obj.summary && obj.summary[key] !== undefined && obj.summary[key] !== null && obj.summary[key] !== '') return obj.summary[key];
      if (obj.live_product_access && obj.live_product_access[key] !== undefined && obj.live_product_access[key] !== null && obj.live_product_access[key] !== '') return obj.live_product_access[key];
    }
    return fallback;
  }

  function findSiteInRows(rows, keys){
    const target = normalise(siteKey);
    if (!target || !Array.isArray(rows)) return null;
    return rows.find(row => keys.some(key => normalise(row && row[key]) === target))
      || rows.find(row => JSON.stringify(row || {}).toLowerCase().includes(target));
  }

  function findRegistrySite(registry){
    return findSiteInRows(registry && registry.sites, ['site_key','key','site_name','name','site_url','url']);
  }

  function findProductSite(productAccess){
    return findSiteInRows(productAccess && productAccess.sites, ['site_key','key','site_name','name','site_url','url']);
  }

  function siteName(regSite, productSite){
    return readAny(regSite, ['site_name','name','site_key','key'], readAny(productSite, ['site_name','name','site_key','key'], siteKey || 'Site Workspace'));
  }

  function siteUrl(regSite, productSite){
    return readAny(regSite, ['site_url','url'], readAny(productSite, ['site_url','url'], 'Unavailable'));
  }

  function siteStatus(regSite, productSite, oauth){
    if (oauth && oauth.coverage_status === 'LIVE_PRODUCT_ACCESS_OK') return 'monitored';
    return readAny(regSite, ['classification','status','state'], readAny(productSite, ['status'], 'Review'));
  }

  function isMonitored(regSite, oauth){
    return !!(oauth && oauth.monitoring_allowed === true) || !!(regSite && (regSite.is_monitored === true || regSite.monitored === true || String(regSite.classification || '').toLowerCase() === 'monitored'));
  }

  function liveRoleRows(productAccess){
    const roles = Array.isArray(productAccess && productAccess.roles) ? productAccess.roles : [];
    const target = normalise(siteKey);
    return roles.filter(row => normalise(row.site_key || row.site_name || row.site_url) === target || JSON.stringify(row).toLowerCase().includes(target));
  }

  function productRows(productAccess, productSite){
    const roles = liveRoleRows(productAccess);
    if (roles.length){
      return roles.map(row => ({
        product: row.role_name || row.role_key || 'Atlassian product',
        users: Number(row.user_count ?? row.jira_product_user_count ?? 0),
        seatLimit: Number(row.seat_limit ?? row.jira_product_seat_limit ?? 0),
        remaining: Number(row.remaining_seats ?? row.jira_product_remaining_seats ?? 0),
        roleCount: 1,
        status: row.status || 'ok',
        source: 'live product access'
      }));
    }
    if (productSite){
      return [{
        product: 'Jira Software',
        users: Number(productSite.jira_product_user_count ?? 0),
        seatLimit: Number(productSite.jira_product_seat_limit ?? 0),
        remaining: Number(productSite.jira_product_remaining_seats ?? 0),
        roleCount: Number(productSite.jira_role_count ?? 0),
        status: productSite.status || 'review',
        source: 'live product access'
      }];
    }
    return [];
  }

  function usersDisplay(row){
    if (!row) return 'Unavailable';
    if (row.seatLimit > 0) return `${row.users} / ${row.seatLimit} (${row.remaining} remaining)`;
    return row.users || row.users === 0 ? String(row.users) : 'Unavailable';
  }

  function productUsers(productSite, rows){
    if (productSite && productSite.jira_product_user_count !== undefined) return productSite.jira_product_user_count;
    if (rows.length) return rows.reduce((max,row) => Math.max(max, Number(row.users || 0)), 0);
    return 'Unavailable';
  }

  function productCount(productSite, rows){
    if (rows.length) return rows.length;
    if (productSite && productSite.jira_role_count !== undefined) return productSite.jira_role_count;
    return productSite ? 'Available' : 'Unavailable';
  }

  function accessRecords(footprint, adminTruth, oauth){
    if (oauth && oauth.named_access_count !== undefined && oauth.named_access_count !== null) return oauth.named_access_count;
    const safe = footprint && footprint.safe_to_show_named_access_ui === true;
    if (!safe) return 'Guarded unavailable';
    return readAny(footprint, ['total_product_access_assignments','users_analyzed','assignment_count'], readAny(adminTruth, ['named_access_count'], 'Unavailable'));
  }

  function renderProductAccess(rows, productSite){
    const body = $('#site-product-access-body');
    if (!body) return;
    if (!rows.length){
      body.innerHTML = '<tr><td colspan="4"><strong>No live product rows available for this site.</strong><br>Backend product access returned no role rows for this site.</td></tr>';
      return;
    }
    body.innerHTML = rows.map(row => `
      <tr>
        <td>${escapeHtml(row.product)}</td>
        <td>${escapeHtml(usersDisplay(row))}</td>
        <td>${escapeHtml(row.roleCount || productSite?.jira_role_count || 'Unavailable')}</td>
        <td><span class="site-badge ${String(row.status).toLowerCase() === 'ok' ? 'site-badge--ok' : 'site-badge--review'}">${escapeHtml(row.status || 'review').toUpperCase()}</span></td>
      </tr>`).join('');
  }

  function renderSignals(regSite, productSite, oauth, footprint, sourceState){
    const list = $('#site-signal-list');
    if (!list) return;
    const liveProduct = sourceState && sourceState.live_product_access;
    const signals = [];
    signals.push({state: regSite ? 'ok' : 'review', text: regSite ? 'Registry contract matched this site.' : 'Registry contract did not find an exact site match.'});
    signals.push({state: productSite ? 'ok' : 'review', text: productSite ? 'Live product access is available for this site.' : 'Live product access did not return this site.'});
    signals.push({state: oauth && oauth.oauth_authorized ? 'ok' : 'review', text: oauth && oauth.oauth_authorized ? 'OAuth coverage is authorised for this site.' : 'OAuth coverage requires review.'});
    signals.push({state: isMonitored(regSite, oauth) ? 'ok' : 'review', text: isMonitored(regSite, oauth) ? 'Monitoring is allowed for this site.' : 'Monitoring is not confirmed for this site.'});
    signals.push({state: footprint && footprint.safe_to_show_named_access_ui === false ? 'review' : 'ok', text: footprint && footprint.safe_to_show_named_access_ui === false ? 'Named user footprint is guarded unavailable and hidden by policy.' : 'User footprint contract is available.'});
    if (liveProduct) signals.push({state: liveProduct.live_collection ? 'ok' : 'review', text: `Live product source status: ${liveProduct.status || 'unavailable'}.`});
    list.innerHTML = signals.map(s => `<li class="site-signal-card site-signal-card--${s.state}"><span class="site-signal-icon">${s.state === 'ok' ? 'OK' : '!'}</span>${escapeHtml(s.text)}</li>`).join('');
    list.classList.add('site-signal-cards');
  }

  function renderSummary(productUsersValue, accessRecordsValue, productSite, sourceState){
    const summary = $('#site-users-summary');
    if (!summary) return;
    const liveProduct = sourceState && sourceState.live_product_access;
    summary.innerHTML = [
      `<span class="site-user-summary-item">Product users: ${escapeHtml(productUsersValue)}</span>`,
      `<span class="site-user-summary-item">Access records: ${escapeHtml(accessRecordsValue)}</span>`,
      `<span class="site-user-summary-item">Seat limit: ${escapeHtml(readAny(productSite, ['jira_product_seat_limit'], 'Unavailable'))}</span>`,
      `<span class="site-user-summary-item">Live source: ${escapeHtml(liveProduct && liveProduct.live_collection ? 'Yes' : 'Review')}</span>`
    ].join('');
    summary.classList.add('site-user-summary-grid');
  }

  function applyBadge(selector){
    const el = $(selector);
    if (!el) return;
    const value = String(el.textContent || '').trim();
    const lower = value.toLowerCase();
    let cls = 'site-badge';
    if (lower.includes('monitored') || lower.includes('ok') || lower.includes('yes') || lower.includes('normal')) cls += ' site-badge--ok';
    else cls += ' site-badge--review';
    el.className = cls;
    el.textContent = value.toUpperCase();
  }

  function renderDiagnostics(payload){
    setText('#site-json-diagnostics', JSON.stringify(payload, null, 2));
  }

  function removeOldNoise(){
    document.querySelectorAll('.jom-layout-breadcrumb, .jom-readiness-strip, .jom-operational-readiness, [data-jom-readiness], [data-jom-operational-readiness]').forEach(el => el.remove());
  }

  async function init(){
    removeOldNoise();
    try {
      const [registry, productAccess, adminTruth, footprint, sourceState, oauth, surface, summary, alerts] = await Promise.all([
        getJson(endpoints.registry),
        getJson(endpoints.productAccess),
        getJson(endpoints.adminTruth),
        getJson(endpoints.footprint),
        getJson(endpoints.sourceState),
        getJson(endpoints.oauthCoverage),
        getJson(endpoints.operatorSurface),
        getJson(endpoints.operatorSummary),
        getJson(endpoints.operatorAlerts)
      ]);

      const regSite = findRegistrySite(registry);
      const productSite = findProductSite(productAccess);
      const rows = productRows(productAccess, productSite);
      const title = siteName(regSite, productSite);
      const users = productUsers(productSite, rows);
      const records = accessRecords(footprint, adminTruth, oauth);
      const products = productCount(productSite, rows);
      const status = siteStatus(regSite, productSite, oauth);

      document.title = 'JOM - ' + title;
      setText('#site-title', title);
      setText('#site-title-breadcrumb', title);
      setText('#site-status-pill', status);
      setText('[data-site-field="key"]', siteKey);
      setText('[data-site-field="url"]', siteUrl(regSite, productSite));
      setText('[data-site-field="monitored"]', isMonitored(regSite, oauth) ? 'Yes' : 'Review');
      setText('[data-site-field="discovery"]', readAny(regSite, ['classification'], status));
      setText('[data-site-field="products"]', products);
      setText('[data-site-field="users"]', users);
      setText('[data-site-field="assignments"]', records);
      setText('[data-site-field="registry-state"]', readAny(regSite, ['classification'], 'Review'));
      setText('[data-site-field="risk"]', isMonitored(regSite, oauth) && productSite ? 'Normal' : 'Review');
      setText('[data-site-field="last-seen"]', readAny(sourceState, ['served_at_utc','generated_at_utc'], readAny(registry, ['generated_at_utc'], 'Unavailable')));

      renderSignals(regSite, productSite, oauth, footprint, sourceState);
      renderProductAccess(rows, productSite);
      renderSummary(users, records, productSite, sourceState);
      applyBadge('#site-status-pill');
      applyBadge('[data-site-field="monitored"]');
      applyBadge('[data-site-field="registry-state"]');
      applyBadge('[data-site-field="risk"]');
      renderDiagnostics({route_site_key: siteKey, registry_match: regSite, product_access_match: productSite, product_rows: rows, oauth_coverage: oauth, source_state: sourceState, user_footprint: footprint, admin_truth_summary: adminTruth && adminTruth.summary, operator_surface: surface, operator_summary: summary, alerts});
    } catch (error){
      setText('#site-title', siteKey || 'Site Workspace');
      setText('#site-status-pill', 'Review');
      setText('#site-json-diagnostics', 'Failed to load site workspace data: ' + error.message);
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
// --- JOM SITE WORKSPACE UI DISPLAY ALIGNMENT v1 END ---

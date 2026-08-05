(function(){
  'use strict';
  const ENDPOINT = '/api/admin/licensing-billing';
  const text = (id, value) => { const el = document.getElementById(id); if (el) el.textContent = value === null || value === undefined || value === '' ? 'Unavailable' : String(value); };
  const html = (id, value) => { const el = document.getElementById(id); if (el) el.innerHTML = value; };
  const esc = value => String(value ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
  const fmt = value => value === null || value === undefined || value === '' ? 'Unavailable' : (Number.isFinite(Number(value)) ? Number(value).toLocaleString() : String(value));
  const badge = value => '<span class="site-badge site-badge--' + (String(value).toLowerCase().includes('ok') || String(value).toLowerCase().includes('live') ? 'ok' : 'review') + '">' + esc(value || 'review') + '</span>';

  function renderActions(actions){
    if (!Array.isArray(actions) || !actions.length) {
      html('lb-action-list', '<article class="admin-lb-action-card"><strong>No immediate licensing actions</strong><p>Current authority-backed licensing checks did not return priority action items.</p></article>');
      return;
    }
    html('lb-action-list', actions.map(item => '<article class="admin-lb-action-card"><span>' + esc(item.level || 'review') + '</span><strong>' + esc(item.title || 'Action required') + '</strong><p>' + esc(item.reason || '') + '</p><p><strong>Next:</strong> ' + esc(item.action || 'Review authority source.') + '</p></article>').join(''));
  }
  function renderProducts(products){
    if (!Array.isArray(products) || !products.length) { html('lb-products-body', '<tr><td colspan="5">No product rows are available from OAuth/Admin authority.</td></tr>'); return; }
    html('lb-products-body', products.map(row => '<tr><td>' + esc(row.product) + '</td><td>' + esc(fmt(row.users)) + '</td><td>' + esc(fmt(row.seat_limit || null)) + '</td><td>' + esc(fmt(row.remaining_seats || null)) + '</td><td>' + badge(row.status || 'ok') + '</td></tr>').join(''));
  }
  function renderSites(sites){
    if (!Array.isArray(sites) || !sites.length) { html('lb-sites-body', '<tr><td colspan="6">No monitored site licensing rows are available from authority.</td></tr>'); return; }
    html('lb-sites-body', sites.map(row => '<tr><td><strong>' + esc(row.site_name || row.site_key) + '</strong><br><small>' + esc(row.site_key || '') + '</small></td><td>' + esc(fmt(row.product_users)) + '</td><td>' + esc(fmt(row.seat_limit)) + '</td><td>' + esc(fmt(row.remaining_seats)) + '</td><td>' + esc(fmt(row.role_count)) + '</td><td>' + badge(row.status || 'review') + '</td></tr>').join(''));
  }
  function renderContacts(payload){
    const contacts = payload && Array.isArray(payload.contacts) ? payload.contacts : [];
    if (!contacts.length) { html('lb-admin-contacts', '<article class="admin-lb-action-card"><span>' + esc((payload && payload.status) || 'unavailable') + '</span><strong>Admin ownership evidence incomplete</strong><p>' + esc((payload && payload.reason) || 'No mapped admin contacts were returned by authority.') + '</p></article>'); return; }
    html('lb-admin-contacts', contacts.slice(0, 6).map(row => '<article class="admin-lb-action-card"><span>' + esc(row.site_key || 'site') + '</span><strong>' + esc(row.display_name || row.email || 'Admin contact') + '</strong><p>' + esc(row.role_source || 'Atlassian Admin role assignment') + '</p></article>').join(''));
  }
  function renderBilling(evidence){
    evidence = evidence || {};
    const fields = [['Invoices', evidence.invoice_data], ['Payment Methods', evidence.payment_methods], ['Renewal Dates', evidence.renewal_dates], ['Commercial Contract', evidence.commercial_contract], ['Billing Account', evidence.billing_account]];
    html('lb-billing-evidence', fields.map(([label,value]) => '<article class="jom-state-card"><span>' + esc(label) + '</span><strong>' + esc(value || 'Unavailable') + '</strong><p>' + esc(evidence.reason || 'Current authority does not prove this billing field.') + '</p></article>').join(''));
  }
  function render(data){
    const authority = data.authority || {}, estate = data.estate || {};
    const actions = Array.isArray(data.actions) ? data.actions : [];
    const products = Array.isArray(data.products) ? data.products : [];
    text('lb-authority-status', data.status === 'ok' ? 'LIVE' : 'REVIEW');
    text('lb-authority-note', authority.truth_policy || 'OAuth/Admin authority only.');
    text('lb-org-count', fmt(estate.organisations));
    text('lb-site-count', fmt(estate.monitored_sites));
    text('lb-product-users', fmt(estate.product_users));
    text('lb-role-rows', fmt(estate.role_rows));
    text('lb-seat-limit', fmt(estate.seat_limit));
    text('lb-remaining-seats', fmt(estate.remaining_seats));
    text('lb-rail-orgs', fmt(estate.organisations));
    text('lb-rail-sites', fmt(estate.monitored_sites));
    text('lb-rail-products', fmt(products.length));
    text('lb-rail-seat-limit', fmt(estate.seat_limit));
    text('lb-rail-users', fmt(estate.product_users));
    text('lb-rail-remaining', fmt(estate.remaining_seats));
    text('lb-rail-billing', authority.commercial_billing || 'unavailable');
    text('lb-rail-actions', fmt(actions.length));
    renderActions(actions);
    renderProducts(products);
    renderSites(data.sites);
    renderBilling(data.billing_evidence);
  }
  function fail(error){
    text('lb-authority-status', 'Unavailable');
    text('lb-authority-note', error && error.message ? error.message : 'Contract unavailable');
    html('lb-action-list', '<article class="admin-lb-action-card"><strong>Contract unavailable</strong><p>Licensing & Billing authority contract could not be loaded.</p></article>');
  }
  function boot(){ fetch(ENDPOINT, {cache:'no-store', headers:{'Accept':'application/json'}}).then(r => { if(!r.ok) throw new Error(ENDPOINT + ' returned HTTP ' + r.status); return r.json(); }).then(render).catch(fail); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
}());

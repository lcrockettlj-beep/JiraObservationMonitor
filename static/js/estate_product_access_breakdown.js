(function () {
  function number(value) {
    const parsed = Number(value || 0);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  function formatNumber(value) { return number(value).toLocaleString(); }
  function setText(id, value) { const el = document.getElementById(id); if (el) el.textContent = value; }
  function statusLabel(row) {
    const status = String(row.status || '').toLowerCase();
    if (status === 'ok') return 'Confirmed';
    if (status === 'error') return 'Blocked';
    return status || 'Unknown';
  }
  function statusClass(row) {
    const status = String(row.status || '').toLowerCase();
    if (status === 'ok') return 'product-access-badge--ok';
    if (status === 'error') return 'product-access-badge--blocked';
    return 'product-access-badge--neutral';
  }
  function renderSites(payload) {
    const body = document.getElementById('estate-product-access-body');
    const empty = document.getElementById('estate-product-access-empty');
    if (!body) return;
    const sites = Array.isArray(payload.sites) ? payload.sites.slice() : [];
    body.innerHTML = '';
    if (!sites.length) {
      if (empty) empty.style.display = 'block';
      return;
    }
    if (empty) empty.style.display = 'none';
    sites.sort(function (a, b) {
      const aUsers = number(a.jira_product_user_count);
      const bUsers = number(b.jira_product_user_count);
      if (bUsers !== aUsers) return bUsers - aUsers;
      return String(a.site_key || '').localeCompare(String(b.site_key || ''));
    });
    sites.forEach(function (site) {
      const row = document.createElement('tr');
      const userCount = number(site.jira_product_user_count);
      const roleCount = number(site.jira_role_count);
      const siteName = site.site_name || site.site_key || 'Unknown site';
      const siteKey = site.site_key || '';
      row.innerHTML = `
        <td>
          <div class="product-access-site-name">${siteName}</div>
          <div class="product-access-site-key">${siteKey}</div>
        </td>
        <td>${formatNumber(userCount)}</td>
        <td>${formatNumber(roleCount)}</td>
        <td><span class="product-access-badge ${statusClass(site)}">${statusLabel(site)}</span></td>
      `;
      body.appendChild(row);
    });
  }
  function renderRoles(payload) {
    const body = document.getElementById('estate-product-access-role-body');
    if (!body) return;
    const roles = Array.isArray(payload.roles) ? payload.roles.slice() : [];
    body.innerHTML = '';
    roles.sort(function (a, b) { return number(b.user_count) - number(a.user_count); });
    roles.forEach(function (role) {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td>
          <div class="product-access-site-name">${role.site_name || role.site_key || 'Unknown site'}</div>
          <div class="product-access-site-key">${role.role_name || role.role_key || 'Jira role'}</div>
        </td>
        <td>${formatNumber(role.user_count)}</td>
        <td>${formatNumber(role.seat_limit)}</td>
        <td>${formatNumber(role.remaining_seats)}</td>
      `;
      body.appendChild(row);
    });
  }
  function render(payload) {
    const summary = payload.summary || {};
    setText('product-access-site-count', formatNumber(summary.sites_with_jira_roles));
    setText('product-access-api-users', formatNumber(summary.total_jira_product_user_count));
    setText('product-access-resource-count', formatNumber(summary.accessible_jira_resource_count));
    setText('product-access-error-count', formatNumber(summary.error_site_count));
    renderSites(payload);
    renderRoles(payload);
  }
  function init() {
    const root = document.getElementById('estate-product-access-breakdown');
    if (!root) return;
    fetch('/static/data/estate_product_access.json', { cache: 'no-store' })
      .then(function (response) { if (!response.ok) throw new Error('estate_product_access.json unavailable'); return response.json(); })
      .then(render)
      .catch(function () { render({ summary: {}, sites: [], roles: [] }); });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();

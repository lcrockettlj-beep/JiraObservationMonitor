(function () {
  function text(value, fallback) { if (value === undefined || value === null || value === '') return fallback || '--'; return String(value); }
  function number(value) { const parsed = Number(value || 0); return Number.isFinite(parsed) ? parsed : 0; }
  function formatNumber(value) { return number(value).toLocaleString(); }
  function categoryLabel(category) { if (category === 'high') return 'High'; if (category === 'medium') return 'Medium'; return 'Low'; }
  function setText(id, value) { const el = document.getElementById(id); if (el) el.textContent = value; }
  function renderRows(users) {
    const body = document.getElementById('estate-footprint-body');
    const empty = document.getElementById('estate-footprint-empty');
    if (!body) return;
    body.innerHTML = '';
    if (!users || users.length === 0) { if (empty) empty.style.display = 'block'; return; }
    if (empty) empty.style.display = 'none';
    users.slice(0, 25).forEach(function (user) {
      const category = user.category || 'low';
      const row = document.createElement('tr');
      const sites = Array.isArray(user.sites) ? user.sites.join(', ') : '--';
      row.innerHTML = `<td><div class="estate-footprint-user">${text(user.name, 'Unknown user')}</div><div class="estate-footprint-email">${text(user.email, 'No email available')}</div></td><td><div class="estate-footprint-sites">${sites || '--'}</div></td><td>${formatNumber(user.site_count)}</td><td><span class="footprint-badge footprint-badge--${category}">${categoryLabel(category)}</span></td>`;
      body.appendChild(row);
    });
  }
  function render(payload) {
    const summary = payload.summary || {};
    setText('footprint-users-analysed', formatNumber(summary.users_analyzed));
    setText('footprint-average-sites', number(summary.average_sites_per_user).toFixed(2));
    setText('footprint-high-count', formatNumber(summary.high_duplication_users));
    setText('footprint-medium-count', formatNumber(summary.medium_duplication_users));
    renderRows(payload.users || []);
  }
  function init() {
    const root = document.getElementById('estate-user-footprint');
    if (!root) return;
    fetch('/static/data/user_footprint.json', { cache: 'no-store' })
      .then(function (response) { if (!response.ok) throw new Error('user_footprint.json unavailable'); return response.json(); })
      .then(render)
      .catch(function () { render({ summary: { users_analyzed: 0, average_sites_per_user: 0, high_duplication_users: 0, medium_duplication_users: 0 }, users: [] }); });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();

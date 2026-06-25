(function () {
  function updateText(id, value) {
    var el = document.getElementById(id);
    if (el) el.textContent = String(value == null ? 0 : value);
  }

  function paint(payload) {
    payload = payload || {};
    updateText('runtimeDisabledUsersHome', payload.disabled_users_total || 0);
    updateText('runtimeJiraUsersHome', payload.jira_users_total || 0);
    updateText('runtimeConfluenceUsersHome', payload.confluence_users_total || 0);
    updateText('runtimeDisabledUsersEstate', payload.disabled_users_total || 0);
    updateText('runtimeJiraUsersEstate', payload.jira_users_total || 0);
    updateText('runtimeConfluenceUsersEstate', payload.confluence_users_total || 0);
  }

  function load() {
    fetch('/api/data', { credentials: 'same-origin' })
      .then(function (response) {
        if (!response.ok) throw new Error('Unable to load /api/data');
        return response.json();
      })
      .then(paint)
      .catch(function () {
        // Keep server-rendered fallback values if the API call fails.
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', load, { once: true });
  } else {
    load();
  }

  window.addEventListener('focus', load);
  window.setInterval(load, 60000);
})();

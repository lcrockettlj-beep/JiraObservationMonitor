(function () {
  'use strict';

  var ENDPOINT = '/api/admin/users-access';

  function getElement(id) {
    return document.getElementById(id);
  }

  function setText(id, value) {
    var element = getElement(id);
    if (!element) return;
    element.textContent = value === null || value === undefined || value === '' ? 'Unavailable' : String(value);
  }

  function setHtml(id, value) {
    var element = getElement(id);
    if (element) element.innerHTML = value;
  }

  function escapeHtml(value) {
    return String(value === null || value === undefined ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function formatValue(value) {
    if (value === null || value === undefined || value === '') return 'Unavailable';
    return isFinite(Number(value)) ? Number(value).toLocaleString() : String(value);
  }

  function authorityLabel(value) {
    var raw = String(value === null || value === undefined ? '' : value).toLowerCase();
    return ['ok', 'live', 'healthy', 'available'].indexOf(raw) >= 0 ? 'Live' : 'Unavailable';
  }

  function formatTime(value) {
    if (!value) return 'Unavailable';
    var date = new Date(value);
    return isNaN(date.getTime()) ? String(value) : date.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' });
  }

  function renderSites(rows) {
    if (!Array.isArray(rows) || !rows.length) {
      setHtml('ua-sites-body', '<tr><td colspan="3">No site access rows available.</td></tr>');
      return;
    }

    setHtml('ua-sites-body', rows.map(function (row) {
      return '<tr>' +
        '<td><strong>' + escapeHtml(row.site_name || row.site_key || 'Unknown') + '</strong><br><small>' + escapeHtml(row.site_key || '') + '</small></td>' +
        '<td>' + escapeHtml(formatValue(row.product_users)) + '</td>' +
        '<td><span class="badge">' + escapeHtml(authorityLabel(row.status)) + '</span></td>' +
        '</tr>';
    }).join(''));
  }

  function renderActions(data) {
    var actions = Array.isArray(data.actions) ? data.actions.filter(function (item) {
      return String(item.level || '').toLowerCase() !== 'ok';
    }) : [];
    var summary = data.summary || {};

    if (Number(summary.mfa_disabled) > 0) {
      actions.unshift({
        title: 'MFA coverage requires review',
        reason: formatValue(summary.mfa_disabled) + ' account(s) are reported without MFA enabled.',
        action: 'Review MFA policy and account exceptions in Atlassian Administration.'
      });
    }

    if (Number(summary.suspended_users) > 0) {
      actions.unshift({
        title: 'Suspended accounts require access review',
        reason: formatValue(summary.suspended_users) + ' suspended account(s) are reported.',
        action: 'Review product and platform-role access for suspended accounts.'
      });
    }

    if (!actions.length) {
      setHtml('ua-action-list', '<article class="action ok"><strong>No immediate account actions</strong><p>Current proven account authority did not return a priority action.</p></article>');
      return;
    }

    setHtml('ua-action-list', actions.slice(0, 8).map(function (item) {
      return '<article class="action">' +
        '<strong>' + escapeHtml(item.title || 'Action required') + '</strong>' +
        '<p>' + escapeHtml(item.reason || '') + '</p>' +
        '<p><b>Next:</b> ' + escapeHtml(item.action || 'Review the affected authority source.') + '</p>' +
        '</article>';
    }).join(''));
  }

  function accountValue(summary, fields, key) {
    return summary[key] !== null && summary[key] !== undefined ? summary[key] : fields[key];
  }

  function render(data) {
    var account = data.account_authority || {};
    var summary = data.summary || {};
    var fields = account.fields || {};
    var authority = data.authority || {};
    var keys = ['org_users', 'managed_users', 'human_users', 'app_accounts', 'mfa_enabled', 'mfa_disabled', 'mfa_unknown', 'suspended_users', 'platform_role_assignments'];

    setText('ua-account-authority', authorityLabel(authority.account_authority));
    setText('ua-authority-note', account.available === true ? 'Privacy-minimised Directory authority is live and fully paginated.' : 'Account authority is unavailable or incomplete.');

    keys.forEach(function (key) {
      setText('ua-' + key.replace(/_/g, '-'), formatValue(accountValue(summary, fields, key)));
    });

    setText('ua-pagination', account.pagination_complete === true ? 'Complete' : 'Unavailable');
    setText('ua-privacy', account.privacy_minimised === true ? 'Enabled' : 'Unavailable');
    setText('ua-directories', formatValue(account.directory_count));
    setText('ua-pages', formatValue(account.page_count));
    setText('ua-active-users', summary.active_users_display || 'Unavailable');
    setText('ua-named-site-access', account.safe_to_show_named_site_access === true ? 'Available' : 'Guarded');
    setText('ua-last-validation', formatTime(data.generated_at_utc));

    renderSites(data.site_access);
    renderActions(data);
  }

  function fail(error) {
    setText('ua-account-authority', 'Unavailable');
    setText('ua-authority-note', error && error.message ? error.message : 'Contract unavailable');
    setHtml('ua-action-list', '<article class="action unavailable"><strong>Users &amp; Access unavailable</strong><p>The authority contract could not be loaded.</p></article>');
  }

  function boot() {
    fetch(ENDPOINT, { cache: 'no-store', headers: { Accept: 'application/json' } })
      .then(function (response) {
        if (!response.ok) throw new Error(ENDPOINT + ' returned HTTP ' + response.status);
        return response.json();
      })
      .then(render)
      .catch(fail);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
}());

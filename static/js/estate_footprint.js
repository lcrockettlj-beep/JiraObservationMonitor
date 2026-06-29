(function () {
  function truth() {
    return window.TruthGuard || {
      safeNumber: function (value) {
        if (value === null || value === undefined || value === '') return null;
        var parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : null;
      },
      applyValue: function (id, value, formatter) {
        var el = document.getElementById(id);
        if (!el) return;
        if (value === null || value === undefined || value === '') {
          el.textContent = 'DATA UNAVAILABLE';
          el.classList.add('truth-unavailable');
          return;
        }
        el.textContent = formatter ? formatter(value) : String(value);
        el.classList.remove('truth-unavailable');
      }
    };
  }

  function esc(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (c) {
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
    });
  }

  function numberOrNull(value) { return truth().safeNumber(value); }
  function formatNumber(value) { return Number(value).toLocaleString(); }

  function setUnavailable(id, label) {
    var el = document.getElementById(id);
    if (!el) return;
    el.textContent = label || 'DATA UNAVAILABLE';
    el.classList.add('truth-unavailable');
  }

  function categoryLabel(category) {
    if (category === 'high') return 'High';
    if (category === 'medium') return 'Medium';
    if (category === 'low') return 'Low';
    return 'Unknown';
  }

  function categoryClass(category) {
    if (category === 'high') return 'estate-footprint-row--high';
    if (category === 'medium') return 'estate-footprint-row--medium';
    if (category === 'low') return 'estate-footprint-row--low';
    return 'estate-footprint-row--unknown';
  }

  function displayText(value, fallback) {
    if (value === null || value === undefined || value === '') return fallback || 'DATA UNAVAILABLE';
    return String(value);
  }

  function showPanelUnavailable(message) {
    setUnavailable('footprint-users-analysed');
    setUnavailable('footprint-average-sites');
    setUnavailable('footprint-high-count');
    setUnavailable('footprint-medium-count');
    var body = document.getElementById('estate-footprint-body');
    var empty = document.getElementById('estate-footprint-empty');
    if (body) body.innerHTML = '';
    if (empty) {
      empty.style.display = 'block';
      empty.textContent = message || 'DATA UNAVAILABLE - user footprint source missing or invalid.';
      empty.classList.add('truth-unavailable');
    }
  }

  function siteList(user) {
    return Array.isArray(user.sites) ? user.sites : [];
  }

  function sourceList(user) {
    return Array.isArray(user.access_sources) ? user.access_sources : [];
  }

  function renderRows(users) {
    var body = document.getElementById('estate-footprint-body');
    var empty = document.getElementById('estate-footprint-empty');
    if (!body) return;
    body.innerHTML = '';
    if (!Array.isArray(users) || users.length === 0) {
      if (empty) {
        empty.style.display = 'block';
        empty.textContent = 'DATA UNAVAILABLE - no verified user footprint rows are available.';
        empty.classList.add('truth-unavailable');
      }
      return;
    }
    if (empty) empty.style.display = 'none';

    users.slice(0, 117).forEach(function (user) {
      var row = document.createElement('tr');
      row.className = categoryClass(user.category);
      row.setAttribute('data-account-id', displayText(user.account_id, ''));

      var sites = siteList(user);
      var sources = sourceList(user);
      var siteCount = numberOrNull(user.site_count);
      var assignments = numberOrNull(user.product_access_assignments);

      var userCell = document.createElement('td');
      var name = document.createElement('strong');
      name.textContent = displayText(user.name, 'Unknown user');
      var email = document.createElement('small');
      email.textContent = displayText(user.email, 'No email available');
      userCell.appendChild(name);
      userCell.appendChild(email);

      var sitesCell = document.createElement('td');
      if (sites.length) {
        sites.forEach(function (site) {
          var pill = document.createElement('span');
          pill.className = 'estate-footprint-site-pill';
          pill.textContent = site;
          sitesCell.appendChild(pill);
        });
      } else {
        sitesCell.textContent = 'DATA UNAVAILABLE';
        sitesCell.classList.add('truth-unavailable');
      }

      var countCell = document.createElement('td');
      var countWrap = document.createElement('div');
      countWrap.className = 'estate-footprint-count-stack';
      var countStrong = document.createElement('strong');
      countStrong.textContent = siteCount === null ? 'DATA UNAVAILABLE' : formatNumber(siteCount);
      var assignmentSmall = document.createElement('small');
      assignmentSmall.textContent = assignments === null ? 'Assignments unavailable' : formatNumber(assignments) + ' product assignment' + (assignments === 1 ? '' : 's');
      countWrap.appendChild(countStrong);
      countWrap.appendChild(assignmentSmall);
      countCell.appendChild(countWrap);

      var categoryCell = document.createElement('td');
      var categoryBadge = document.createElement('span');
      categoryBadge.className = 'estate-footprint-category estate-footprint-category--' + (user.category || 'unknown');
      categoryBadge.textContent = categoryLabel(user.category || 'unknown');
      categoryCell.appendChild(categoryBadge);
      if (sources.length) {
        var sourceSmall = document.createElement('small');
        sourceSmall.className = 'estate-footprint-source-note';
        sourceSmall.textContent = 'Source: ' + sources.join(' + ');
        categoryCell.appendChild(sourceSmall);
      }

      row.appendChild(userCell);
      row.appendChild(sitesCell);
      row.appendChild(countCell);
      row.appendChild(categoryCell);
      body.appendChild(row);
    });
  }

  function render(payload) {
    if (!payload || payload.source_status !== 'generated' || payload.safe_to_show_named_access_ui !== true || !payload.summary) {
      showPanelUnavailable((payload && payload.reason) || 'DATA UNAVAILABLE - named access is not safe to show.');
      return;
    }
    var summary = payload.summary;
    truth().applyValue('footprint-users-analysed', numberOrNull(summary.users_analyzed), formatNumber);
    truth().applyValue('footprint-average-sites', numberOrNull(summary.average_sites_per_user), function (value) { return Number(value).toFixed(2); });
    truth().applyValue('footprint-high-count', numberOrNull(summary.high_duplication_users), formatNumber);
    truth().applyValue('footprint-medium-count', numberOrNull(summary.medium_duplication_users), formatNumber);
    renderRows(payload.users || []);
  }

  function init() {
    var root = document.getElementById('estate-user-footprint');
    if (!root) return;
    fetch('/static/data/user_footprint.json', { cache: 'no-store' })
      .then(function (response) {
        if (!response.ok) throw new Error('user_footprint.json unavailable');
        return response.json();
      })
      .then(render)
      .catch(function () {
        showPanelUnavailable('DATA UNAVAILABLE - user_footprint.json is missing or failed to load.');
      });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();

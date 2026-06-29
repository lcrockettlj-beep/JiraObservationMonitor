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
      }
    };
  }

  function numberOrNull(value) {
    return truth().safeNumber(value);
  }

  function formatNumber(value) {
    return Number(value).toLocaleString();
  }

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

    users.slice(0, 25).forEach(function (user) {
      var row = document.createElement('tr');
      var sites = Array.isArray(user.sites) ? user.sites.join(', ') : 'DATA UNAVAILABLE';
      var siteCount = numberOrNull(user.site_count);

      var userCell = document.createElement('td');
      var name = document.createElement('strong');
      name.textContent = displayText(user.name, 'Unknown user');
      var email = document.createElement('small');
      email.textContent = displayText(user.email, 'No email available');
      userCell.appendChild(name);
      userCell.appendChild(email);

      var sitesCell = document.createElement('td');
      sitesCell.textContent = sites;

      var countCell = document.createElement('td');
      if (siteCount === null) {
        countCell.textContent = 'DATA UNAVAILABLE';
        countCell.classList.add('truth-unavailable');
      } else {
        countCell.textContent = formatNumber(siteCount);
      }

      var categoryCell = document.createElement('td');
      categoryCell.textContent = categoryLabel(user.category || 'unknown');

      row.appendChild(userCell);
      row.appendChild(sitesCell);
      row.appendChild(countCell);
      row.appendChild(categoryCell);
      body.appendChild(row);
    });
  }

  function render(payload) {
    if (!payload || !payload.summary) {
      showPanelUnavailable('DATA UNAVAILABLE - user footprint source missing or invalid.');
      return;
    }

    var summary = payload.summary;
    var usersAnalysed = numberOrNull(summary.users_analyzed);
    var averageSites = numberOrNull(summary.average_sites_per_user);
    var highDuplication = numberOrNull(summary.high_duplication_users);
    var mediumDuplication = numberOrNull(summary.medium_duplication_users);

    truth().applyValue('footprint-users-analysed', usersAnalysed, formatNumber);
    truth().applyValue('footprint-average-sites', averageSites, function (value) { return Number(value).toFixed(2); });
    truth().applyValue('footprint-high-count', highDuplication, formatNumber);
    truth().applyValue('footprint-medium-count', mediumDuplication, formatNumber);

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

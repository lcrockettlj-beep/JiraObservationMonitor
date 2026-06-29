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
      },
      applyRatio: function (id, a, b) {
        var el = document.getElementById(id);
        if (!el) return;
        if (!a || !b || a <= 0) {
          el.textContent = 'DATA UNAVAILABLE';
          el.classList.add('truth-unavailable');
          return;
        }
        el.textContent = (b / a).toFixed(2);
      }
    };
  }

  function formatNumber(value) {
    return Number(value).toLocaleString();
  }

  function sourceLine(label) {
    return '<br><span class="truth-source">Source: ' + label + '</span>';
  }

  function statusText(summary) {
    var guard = truth();
    var apiUsers = guard.safeNumber(summary.api_product_user_count);
    var billingSeats = guard.safeNumber(summary.billing_jira_seats);
    var sitesWithRoles = guard.safeNumber(summary.sites_with_jira_roles);
    var resources = guard.safeNumber(summary.accessible_jira_resource_count);

    if (apiUsers === null || billingSeats === null) {
      return 'DATA UNAVAILABLE - product/billing comparison source is incomplete.';
    }

    var label = apiUsers === billingSeats ? 'API product access aligned with billing' : 'API product access comparison active';
    return label + ': ' + formatNumber(apiUsers) + ' API product users, ' + formatNumber(billingSeats) + ' billing seats, ' +
      (sitesWithRoles === null ? 'DATA UNAVAILABLE' : formatNumber(sitesWithRoles)) + ' of ' +
      (resources === null ? 'DATA UNAVAILABLE' : formatNumber(resources)) + ' accessible Jira resources confirmed.';
  }

  function buildInsight(summary) {
    var guard = truth();
    var apiUsers = guard.safeNumber(summary.api_product_user_count);
    var humans = guard.safeNumber(summary.admin_human_users);
    var billingSeats = guard.safeNumber(summary.billing_jira_seats);
    var resources = guard.safeNumber(summary.accessible_jira_resource_count);
    var sitesWithRoles = guard.safeNumber(summary.sites_with_jira_roles);
    var source = 'estate_access_truth.json latest generated snapshot';

    if (apiUsers !== null && billingSeats !== null && humans !== null && apiUsers === billingSeats) {
      var ratio = humans > 0 ? (billingSeats / humans).toFixed(2) : 'DATA UNAVAILABLE';
      return formatNumber(humans) + ' human users are compared against ' + formatNumber(billingSeats) + ' Jira seats. API product access also reports ' + formatNumber(apiUsers) + ' Jira product users, so billing and API product access are aligned at ' + ratio + ' seats per human. Product access is confirmed on ' + (sitesWithRoles === null ? 'DATA UNAVAILABLE' : formatNumber(sitesWithRoles)) + ' of ' + (resources === null ? 'DATA UNAVAILABLE' : formatNumber(resources)) + ' accessible Jira resources.' + sourceLine(source);
    }

    if (apiUsers !== null && billingSeats !== null && apiUsers !== billingSeats) {
      return 'API product access reports ' + formatNumber(apiUsers) + ' users while billing reports ' + formatNumber(billingSeats) + ' seats. Review before treating product access as final licence truth.' + sourceLine(source);
    }

    return 'DATA UNAVAILABLE - Estate product access truth is not complete enough to compare billing and API product access.' + sourceLine(source);
  }

  function ensureStatusNode(summary) {
    var root = document.getElementById('estate-trust-intelligence');
    if (!root) return;
    var status = document.getElementById('estate-product-truth-status');
    if (!status) {
      status = document.createElement('div');
      status.id = 'estate-product-truth-status';
      status.style.marginTop = '12px';
      status.style.padding = '12px 14px';
      status.style.borderRadius = '14px';
      status.style.border = '1px solid rgba(255,255,255,0.12)';
      status.style.background = 'rgba(255,255,255,0.045)';
      status.style.color = 'var(--muted)';
      status.style.fontSize = '12px';
      status.style.lineHeight = '1.45';
      root.appendChild(status);
    }
    status.innerHTML = statusText(summary) + sourceLine('Jira API product roles, latest generated snapshot');
  }

  function setSeverityClass(id, humans, seats) {
    var el = document.getElementById(id);
    if (!el) return;
    el.classList.remove('estate-trust-card__value--warning', 'estate-trust-card__value--critical');
    if (humans === null || seats === null || humans <= 0 || seats <= 0) return;
    var ratio = seats / humans;
    if (ratio >= 2) el.classList.add('estate-trust-card__value--critical');
    else if (ratio >= 1.3) el.classList.add('estate-trust-card__value--warning');
  }

  function applyProductTruth(payload) {
    var guard = truth();
    var summary = payload && payload.summary ? payload.summary : null;
    if (!summary) {
      ensureStatusNode({});
      return;
    }

    var humans = guard.safeNumber(summary.admin_human_users);
    var billingSeats = guard.safeNumber(summary.billing_jira_seats);
    var apiUsers = guard.safeNumber(summary.api_product_user_count);
    var effectiveSeats = billingSeats !== null ? billingSeats : apiUsers;

    guard.applyValue('estate-trust-human-users', humans, formatNumber);
    guard.applyValue('estate-trust-jira-seats', effectiveSeats, formatNumber);
    guard.applyRatio('estate-trust-seat-ratio', humans, effectiveSeats);

    var insight = document.getElementById('estate-trust-insight');
    if (insight) insight.innerHTML = buildInsight(summary);

    setSeverityClass('estate-trust-jira-seats', humans, effectiveSeats);
    setSeverityClass('estate-trust-seat-ratio', humans, effectiveSeats);
    ensureStatusNode(summary);
  }

  function init() {
    var root = document.getElementById('estate-trust-intelligence');
    if (!root) return;

    fetch('/static/data/estate_access_truth.json', { cache: 'no-store' })
      .then(function (response) {
        if (!response.ok) throw new Error('estate_access_truth.json unavailable');
        return response.json();
      })
      .then(applyProductTruth)
      .catch(function () {
        applyProductTruth(null);
      });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();

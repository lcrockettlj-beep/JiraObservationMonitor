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

  function setSeverityClass(id, humans, seats) {
    var el = document.getElementById(id);
    if (!el) return;
    el.classList.remove('estate-trust-card__value--warning', 'estate-trust-card__value--critical');
    if (humans === null || seats === null || humans <= 0 || seats <= 0) return;
    var ratio = seats / humans;
    if (ratio >= 2) el.classList.add('estate-trust-card__value--critical');
    else if (ratio >= 1.3) el.classList.add('estate-trust-card__value--warning');
  }

  function sourceLine(label) {
    return '<br><span class="truth-source">Source: ' + label + '</span>';
  }

  function buildInsight(totalIdentities, humanUsers, jiraSeats, seatSites, sourceLabel) {
    var source = sourceLabel || 'Estate runtime context';
    if (humanUsers === null) return 'Human-user identity truth is unavailable.' + sourceLine(source);
    if (jiraSeats === null) return 'Jira seat usage is unavailable for the monitored Estate.' + sourceLine(source);
    if (humanUsers <= 0) return 'Human-user baseline is zero or unavailable, so seat ratio cannot be trusted.' + sourceLine(source);

    var ratio = jiraSeats / humanUsers;
    var siteText = seatSites !== null && seatSites > 0 ? ' across ' + formatNumber(seatSites) + ' monitored Jira site' + (seatSites === 1 ? '' : 's') : '';
    var identityText = totalIdentities !== null ? ' Estate identity enrichment is currently surfacing ' + formatNumber(totalIdentities) + ' total organisation identities.' : '';

    if (ratio >= 2) {
      return formatNumber(humanUsers) + ' human users hold ' + formatNumber(jiraSeats) + ' Jira seats' + siteText + ', creating a ' + ratio.toFixed(2) + ' seats-per-human ratio. This indicates high multi-site access duplication.' + identityText + sourceLine(source);
    }
    if (ratio >= 1.3) {
      return formatNumber(humanUsers) + ' human users hold ' + formatNumber(jiraSeats) + ' Jira seats' + siteText + ', creating a ' + ratio.toFixed(2) + ' seats-per-human ratio. This indicates moderate multi-site overlap.' + identityText + sourceLine(source);
    }
    return formatNumber(humanUsers) + ' human users hold ' + formatNumber(jiraSeats) + ' Jira seats' + siteText + ', creating a ' + ratio.toFixed(2) + ' seats-per-human ratio.' + identityText + sourceLine(source);
  }

  function renderEstateTrust(values) {
    var guard = truth();
    var totalIdentities = guard.safeNumber(values.totalIdentities);
    var humanUsers = guard.safeNumber(values.humanUsers);
    var jiraSeats = guard.safeNumber(values.jiraSeats);
    var seatSites = guard.safeNumber(values.seatSites);
    var sourceLabel = values.sourceLabel || 'Estate runtime context';

    guard.applyValue('estate-trust-total-identities', totalIdentities, formatNumber);
    guard.applyValue('estate-trust-human-users', humanUsers, formatNumber);
    guard.applyValue('estate-trust-jira-seats', jiraSeats, formatNumber);
    guard.applyRatio('estate-trust-seat-ratio', humanUsers, jiraSeats);

    var insight = document.getElementById('estate-trust-insight');
    if (insight) insight.innerHTML = buildInsight(totalIdentities, humanUsers, jiraSeats, seatSites, sourceLabel);

    setSeverityClass('estate-trust-jira-seats', humanUsers, jiraSeats);
    setSeverityClass('estate-trust-seat-ratio', humanUsers, jiraSeats);
  }

  function initEstateTrust() {
    var root = document.getElementById('estate-trust-intelligence');
    if (!root) return;

    var baseValues = {
      totalIdentities: root.dataset.totalIdentities,
      humanUsers: root.dataset.humanUsers,
      jiraSeats: root.dataset.jiraSeats,
      seatSites: root.dataset.seatSites,
      sourceLabel: 'Estate runtime context from latest collector render'
    };

    renderEstateTrust(baseValues);

    fetch('/static/data/billing_seats.json', { cache: 'no-store' })
      .then(function (response) {
        if (!response.ok) throw new Error('billing_seats.json unavailable');
        return response.json();
      })
      .then(function (payload) {
        renderEstateTrust({
          totalIdentities: baseValues.totalIdentities,
          humanUsers: baseValues.humanUsers,
          jiraSeats: payload.total_jira_seats,
          seatSites: payload.jira_site_count,
          sourceLabel: (payload.source || 'billing_seats.json') + ' snapshot'
        });
      })
      .catch(function () {
        renderEstateTrust(baseValues);
      });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initEstateTrust);
  else initEstateTrust();
})();

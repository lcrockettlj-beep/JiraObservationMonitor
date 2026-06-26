(function () {
  function number(value) {
    const parsed = Number(value || 0);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function formatNumber(value) {
    return number(value).toLocaleString();
  }

  function ratioText(humans, seats) {
    const humanCount = number(humans);
    const seatCount = number(seats);
    if (humanCount <= 0 || seatCount <= 0) return '--';
    return (seatCount / humanCount).toFixed(2);
  }

  function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  }

  function setSeverityClass(id, humans, seats) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.remove('estate-trust-card__value--warning', 'estate-trust-card__value--critical');
    const humanCount = number(humans);
    const seatCount = number(seats);
    if (humanCount <= 0 || seatCount <= 0) return;
    const ratio = seatCount / humanCount;
    if (ratio >= 2) {
      el.classList.add('estate-trust-card__value--critical');
    } else if (ratio >= 1.3) {
      el.classList.add('estate-trust-card__value--warning');
    }
  }

  function buildInsight(summary) {
    const apiUsers = number(summary.api_product_user_count);
    const humans = number(summary.admin_human_users);
    const billingSeats = number(summary.billing_jira_seats);
    const apiRatio = number(summary.api_product_to_human_ratio);
    const billingRatio = number(summary.billing_to_human_ratio);
    const resources = number(summary.accessible_jira_resource_count);
    const sitesWithRoles = number(summary.sites_with_jira_roles);

    if (apiUsers > 0 && billingSeats > 0 && apiUsers === billingSeats) {
      return `${formatNumber(humans)} human users are compared against ${formatNumber(billingSeats)} Jira seats. API product access also reports ${formatNumber(apiUsers)} Jira product users, so billing and API product access are aligned at ${billingRatio.toFixed(2)} seats per human. Product access is currently confirmed on ${formatNumber(sitesWithRoles)} of ${formatNumber(resources)} accessible Jira resources.`;
    }

    if (apiUsers > 0 && billingSeats > 0 && apiUsers !== billingSeats) {
      return `${formatNumber(humans)} human users are compared against ${formatNumber(billingSeats)} billing seats, while API product access reports ${formatNumber(apiUsers)} Jira product users. This indicates a difference between billing and API product-role data that should be reviewed before using product access as final licence truth.`;
    }

    if (billingSeats > 0) {
      return `${formatNumber(humans)} human users are compared against ${formatNumber(billingSeats)} Jira billing seats (${billingRatio.toFixed(2)} seats per human). API product access is not currently available for the full estate, so billing remains the active licence truth.`;
    }

    return 'Estate product access truth is not currently available. Billing and API product access values are waiting for source data.';
  }

  function ensureStatusNode(summary) {
    const root = document.getElementById('estate-trust-intelligence');
    if (!root) return;

    let status = document.getElementById('estate-product-truth-status');
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

    const apiUsers = number(summary.api_product_user_count);
    const billingSeats = number(summary.billing_jira_seats);
    const sitesWithRoles = number(summary.sites_with_jira_roles);
    const resources = number(summary.accessible_jira_resource_count);
    const aligned = apiUsers > 0 && billingSeats > 0 && apiUsers === billingSeats;
    const label = aligned ? 'API product access aligned with billing' : 'API product access comparison active';
    status.textContent = `${label}: ${formatNumber(apiUsers)} API product users, ${formatNumber(billingSeats)} billing seats, ${formatNumber(sitesWithRoles)} of ${formatNumber(resources)} accessible Jira resources confirmed.`;
  }

  function applyProductTruth(payload) {
    const summary = payload && payload.summary ? payload.summary : {};
    const humans = number(summary.admin_human_users);
    const billingSeats = number(summary.billing_jira_seats);
    const apiUsers = number(summary.api_product_user_count);
    const effectiveSeats = billingSeats || apiUsers;

    if (humans > 0) setText('estate-trust-human-users', formatNumber(humans));
    if (effectiveSeats > 0) setText('estate-trust-jira-seats', formatNumber(effectiveSeats));
    if (humans > 0 && effectiveSeats > 0) setText('estate-trust-seat-ratio', ratioText(humans, effectiveSeats));

    const insight = document.getElementById('estate-trust-insight');
    if (insight) insight.textContent = buildInsight(summary);

    setSeverityClass('estate-trust-jira-seats', humans, effectiveSeats);
    setSeverityClass('estate-trust-seat-ratio', humans, effectiveSeats);
    ensureStatusNode(summary);
  }

  function init() {
    const root = document.getElementById('estate-trust-intelligence');
    if (!root) return;

    fetch('/static/data/estate_access_truth.json', { cache: 'no-store' })
      .then(function (response) {
        if (!response.ok) throw new Error('estate_access_truth.json unavailable');
        return response.json();
      })
      .then(applyProductTruth)
      .catch(function () {
        // Leave existing billing binding in place if product truth is not available.
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

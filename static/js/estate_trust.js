(function () {
  function formatNumber(value) {
    const number = Number(value || 0);
    if (!Number.isFinite(number)) return '0';
    return number.toLocaleString();
  }

  function ratioText(humans, seats) {
    if (!humans || humans <= 0 || !seats || seats <= 0) return '--';
    return (seats / humans).toFixed(2);
  }

  function insightText(humans, seats, totalIdentities, seatSites, sourceLabel) {
    const sourceText = sourceLabel ? ` Source: ${sourceLabel}.` : '';
    if (!humans || humans <= 0) {
      return `Human-user identity truth is not currently available, so Estate cannot compare seat usage against the real user baseline.${sourceText}`;
    }
    if (!seats || seats <= 0) {
      return `Jira seat usage is not currently available for the monitored Estate. The trust layer is ready, but the seat comparison is waiting for billing-seat inputs.${sourceText}`;
    }
    const ratio = seats / humans;
    const ratioDisplay = ratio.toFixed(2);
    const siteText = seatSites && seatSites > 0 ? ` across ${formatNumber(seatSites)} monitored Jira site${seatSites === 1 ? '' : 's'}` : '';
    const identityText = totalIdentities && totalIdentities > 0 ? ` Estate identity enrichment is currently surfacing ${formatNumber(totalIdentities)} total organisation identities.` : '';
    if (ratio >= 2) {
      return `${formatNumber(humans)} human users hold ${formatNumber(seats)} Jira seats${siteText}, creating a ${ratioDisplay} seats-per-human ratio. This indicates high multi-site access duplication and potential licence inefficiency.${identityText}${sourceText}`;
    }
    if (ratio >= 1.3) {
      return `${formatNumber(humans)} human users hold ${formatNumber(seats)} Jira seats${siteText}, creating a ${ratioDisplay} seats-per-human ratio. This indicates moderate multi-site overlap that should be reviewed before expanding licence coverage.${identityText}${sourceText}`;
    }
    return `${formatNumber(humans)} human users hold ${formatNumber(seats)} Jira seats${siteText}, creating a ${ratioDisplay} seats-per-human ratio. Seat usage is currently close to the human-user baseline.${identityText}${sourceText}`;
  }

  function applySeverityClass(target, humans, seats) {
    if (!target) return;
    target.classList.remove('estate-trust-card__value--warning', 'estate-trust-card__value--critical');
    if (!humans || humans <= 0 || !seats || seats <= 0) return;
    const ratio = seats / humans;
    if (ratio >= 2) target.classList.add('estate-trust-card__value--critical');
    else if (ratio >= 1.3) target.classList.add('estate-trust-card__value--warning');
  }

  function renderEstateTrust(values) {
    const totalIdentities = Number(values.totalIdentities || 0);
    const humanUsers = Number(values.humanUsers || 0);
    const jiraSeats = Number(values.jiraSeats || 0);
    const seatSites = Number(values.seatSites || 0);
    const sourceLabel = values.sourceLabel || '';
    const totalEl = document.getElementById('estate-trust-total-identities');
    const humanEl = document.getElementById('estate-trust-human-users');
    const seatsEl = document.getElementById('estate-trust-jira-seats');
    const ratioEl = document.getElementById('estate-trust-seat-ratio');
    const insightEl = document.getElementById('estate-trust-insight');
    if (totalEl) totalEl.textContent = formatNumber(totalIdentities);
    if (humanEl) humanEl.textContent = formatNumber(humanUsers);
    if (seatsEl) seatsEl.textContent = jiraSeats === 0 ? '--' : formatNumber(jiraSeats);
    if (ratioEl) ratioEl.textContent = ratioText(humanUsers, jiraSeats);
    if (insightEl) insightEl.textContent = insightText(humanUsers, jiraSeats, totalIdentities, seatSites, sourceLabel);
    applySeverityClass(ratioEl, humanUsers, jiraSeats);
    applySeverityClass(seatsEl, humanUsers, jiraSeats);
  }

  function initEstateTrust() {
    const root = document.getElementById('estate-trust-intelligence');
    if (!root) return;
    const baseValues = {
      totalIdentities: Number(root.dataset.totalIdentities || 0),
      humanUsers: Number(root.dataset.humanUsers || 0),
      jiraSeats: Number(root.dataset.jiraSeats || 0),
      seatSites: Number(root.dataset.seatSites || 0),
      sourceLabel: 'Estate runtime context'
    };
    renderEstateTrust(baseValues);
    fetch('/static/data/billing_seats.json', { cache: 'no-store' })
      .then(function (response) { if (!response.ok) throw new Error('billing_seats.json unavailable'); return response.json(); })
      .then(function (payload) {
        renderEstateTrust({
          totalIdentities: baseValues.totalIdentities,
          humanUsers: baseValues.humanUsers,
          jiraSeats: Number(payload.total_jira_seats || 0),
          seatSites: Number(payload.jira_site_count || 0),
          sourceLabel: payload.source || 'billing_catalog.py static billing snapshot'
        });
      })
      .catch(function () { renderEstateTrust(baseValues); });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initEstateTrust);
  else initEstateTrust();
})();

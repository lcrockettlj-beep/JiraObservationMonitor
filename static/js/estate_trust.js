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

  function insightText(humans, seats, totalIdentities, seatSites) {
    if (!humans || humans <= 0) {
      return 'Human user truth is not currently available to compare against seat usage on this estate page.';
    }
    if (!seats || seats <= 0) {
      return 'Jira seat usage is not currently available on the Estate page, so the seat comparison layer is waiting for seat inputs.';
    }
    const ratio = seats / humans;
    const identityNote = totalIdentities && totalIdentities > 0
      ? ` Admin enrichment is currently surfacing ${formatNumber(totalIdentities)} total identities across the organisation.`
      : '';
    const seatSiteNote = seatSites && seatSites > 0
      ? ` Seat data is currently known for ${formatNumber(seatSites)} monitored Jira site${seatSites === 1 ? '' : 's'}.`
      : '';

    if (ratio >= 2) {
      return `High multi-site duplication detected: ${formatNumber(seats)} Jira seats are being compared against ${formatNumber(humans)} human users (${ratio.toFixed(2)} seats per human).${seatSiteNote}${identityNote}`;
    }
    if (ratio >= 1.3) {
      return `Moderate multi-site overlap detected: ${formatNumber(seats)} Jira seats are being compared against ${formatNumber(humans)} human users (${ratio.toFixed(2)} seats per human).${seatSiteNote}${identityNote}`;
    }
    return `Seat usage is currently close to the human-user baseline: ${formatNumber(seats)} Jira seats versus ${formatNumber(humans)} human users (${ratio.toFixed(2)} seats per human).${seatSiteNote}${identityNote}`;
  }

  function applySeverityClass(target, humans, seats) {
    if (!target) return;
    target.classList.remove('estate-trust-card__value--warning', 'estate-trust-card__value--critical');
    if (!humans || humans <= 0 || !seats || seats <= 0) return;
    const ratio = seats / humans;
    if (ratio >= 2) {
      target.classList.add('estate-trust-card__value--critical');
      return;
    }
    if (ratio >= 1.3) {
      target.classList.add('estate-trust-card__value--warning');
    }
  }

  function initEstateTrust() {
    const root = document.getElementById('estate-trust-intelligence');
    if (!root) return;

    const totalIdentities = Number(root.dataset.totalIdentities || 0);
    const humanUsers = Number(root.dataset.humanUsers || 0);
    const jiraSeats = Number(root.dataset.jiraSeats || 0);
    const seatSites = Number(root.dataset.seatSites || 0);

    const totalEl = document.getElementById('estate-trust-total-identities');
    const humanEl = document.getElementById('estate-trust-human-users');
    const seatsEl = document.getElementById('estate-trust-jira-seats');
    const ratioEl = document.getElementById('estate-trust-seat-ratio');
    const insightEl = document.getElementById('estate-trust-insight');

    
    if (totalEl) totalEl.textContent = formatNumber(totalIdentities);
    if (humanEl) humanEl.textContent = formatNumber(humanUsers);

    if (seatsEl) {
      seatsEl.textContent = jiraSeats === 0 ? '--' : formatNumber(jiraSeats);
    }

    if (ratioEl) ratioEl.textContent = ratioText(humanUsers, jiraSeats);
    if (insightEl) insightEl.textContent = insightText(humanUsers, jiraSeats, totalIdentities, seatSites);

    applySeverityClass(ratioEl, humanUsers, jiraSeats);
    applySeverityClass(seatsEl, humanUsers, jiraSeats);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initEstateTrust);
  } else {
    initEstateTrust();
  }
})();

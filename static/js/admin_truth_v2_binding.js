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

  function formatNumber(value) {
    return Number(value).toLocaleString();
  }

  function badge(status) {
    return status === 'aligned' ? 'Aligned' : (status || 'Unknown');
  }

  function severityClass(severity) {
    if (severity === 'ok') return 'truth-badge--ok';
    if (severity === 'critical') return 'truth-badge--critical';
    return 'truth-badge--warning';
  }

  function sourceLine(payload) {
    var generated = payload && payload.generated_at_utc ? payload.generated_at_utc : 'timestamp unavailable';
    return '<br><span class="truth-source">Source: Admin Truth Layer v2 snapshot (' + generated + ')</span>';
  }

  function panel(rootId, title, subtitle) {
    var root = document.getElementById(rootId);
    if (!root) return null;
    if (document.getElementById(rootId + '-card')) return document.getElementById(rootId + '-card');

    var card = document.createElement('section');
    card.id = rootId + '-card';
    card.className = 'admin-truth-v2-card signal-border';
    card.innerHTML = '' +
      '<div class="admin-truth-v2-head">' +
      '<div><h3>' + title + '</h3><p>' + subtitle + '</p></div>' +
      '<span id="' + rootId + '-status" class="truth-badge">Loading</span>' +
      '</div>' +
      '<div class="admin-truth-v2-grid">' +
      '<article><span>Human users</span><strong id="' + rootId + '-humans">DATA UNAVAILABLE</strong><small>Admin identity truth</small></article>' +
      '<article><span>Billing seats</span><strong id="' + rootId + '-billing">DATA UNAVAILABLE</strong><small>Commercial truth</small></article>' +
      '<article><span>API product users</span><strong id="' + rootId + '-api">DATA UNAVAILABLE</strong><small>Application role count</small></article>' +
      '<article><span>Variance</span><strong id="' + rootId + '-variance">DATA UNAVAILABLE</strong><small>API minus billing</small></article>' +
      '<article><span>Ratio</span><strong id="' + rootId + '-ratio">DATA UNAVAILABLE</strong><small>Seats per human</small></article>' +
      '<article><span>Confirmed product sites</span><strong id="' + rootId + '-sites">DATA UNAVAILABLE</strong><small>API-visible Jira resources</small></article>' +
      '</div>' +
      '<p id="' + rootId + '-insight" class="admin-truth-v2-insight">Waiting for Admin Truth Layer v2.</p>' +
      '<p id="' + rootId + '-guard" class="admin-truth-v2-guard">Named user-to-site footprint remains hidden until a Directory-equivalent source is verified.</p>';

    var anchor = root.querySelector('.section-header') || root.firstElementChild;
    if (anchor && anchor.nextSibling) root.insertBefore(card, anchor.nextSibling);
    else root.appendChild(card);
    return card;
  }

  function apply(rootId, payload) {
    var guard = truth();
    var summary = payload && payload.summary ? payload.summary : {};
    var controls = payload && payload.controls ? payload.controls : {};

    var status = document.getElementById(rootId + '-status');
    if (status) {
      status.textContent = badge(summary.status);
      status.className = 'truth-badge ' + severityClass(summary.severity);
    }

    var humans = guard.safeNumber(summary.admin_human_users);
    var billing = guard.safeNumber(summary.billing_jira_seats);
    var api = guard.safeNumber(summary.api_product_users);
    var variance = guard.safeNumber(summary.api_minus_billing);
    var ratio = guard.safeNumber(summary.billing_to_human_ratio);
    var confirmed = guard.safeNumber(summary.confirmed_product_site_count);
    var accessible = guard.safeNumber(summary.accessible_jira_resource_count);

    guard.applyValue(rootId + '-humans', humans, formatNumber);
    guard.applyValue(rootId + '-billing', billing, formatNumber);
    guard.applyValue(rootId + '-api', api, formatNumber);
    guard.applyValue(rootId + '-variance', variance, function (value) { return String(value); });
    guard.applyValue(rootId + '-ratio', ratio, function (value) { return Number(value).toFixed(2); });

    var sitesEl = document.getElementById(rootId + '-sites');
    if (sitesEl) {
      if (confirmed === null || accessible === null) {
        sitesEl.textContent = 'DATA UNAVAILABLE';
        sitesEl.classList.add('truth-unavailable');
      } else {
        sitesEl.textContent = formatNumber(confirmed) + ' / ' + formatNumber(accessible);
      }
    }

    var insight = document.getElementById(rootId + '-insight');
    if (insight) insight.innerHTML = (summary.interpretation || 'Admin Truth Layer v2 loaded without interpretation.') + sourceLine(payload);

    var guardText = document.getElementById(rootId + '-guard');
    if (guardText) guardText.innerHTML = (controls.named_user_footprint_guard_reason || 'Named user-to-site footprint remains hidden until verified.') + sourceLine(payload);
  }

  function unavailable(rootId) {
    var status = document.getElementById(rootId + '-status');
    if (status) {
      status.textContent = 'Unavailable';
      status.className = 'truth-badge truth-badge--critical';
    }
    ['humans', 'billing', 'api', 'variance', 'ratio', 'sites'].forEach(function (field) {
      var el = document.getElementById(rootId + '-' + field);
      if (el) {
        el.textContent = 'DATA UNAVAILABLE';
        el.classList.add('truth-unavailable');
      }
    });
    var insight = document.getElementById(rootId + '-insight');
    if (insight) insight.textContent = 'DATA UNAVAILABLE - admin_truth_v2.json is missing or failed to load.';
  }

  function init() {
    var isReference = location.pathname.indexOf('/reference') === 0;
    var isAdmin = location.pathname.indexOf('/admin') === 0;
    var isEstate = location.pathname.indexOf('/estate') === 0;
    if (!isAdmin && !isEstate && !isReference) return;

    var estateRoot = document.getElementById('estate-trust-intelligence') || document.querySelector('body');
    var adminRoot = document.querySelector('body');
    var rootId = isEstate ? 'estate-admin-truth-v2' : 'admin-truth-v2';
    var containerId = rootId + '-mount';
    var mount = document.getElementById(containerId);

    if (!mount) {
      mount = document.createElement('div');
      mount.id = containerId;
      (isEstate ? estateRoot : adminRoot).appendChild(mount);
    }

    panel(containerId, 'Admin Truth Layer v2', 'Verified comparison between Admin identity, Atlassian billing, and Jira API product access.');

    fetch('/static/data/admin_truth_v2.json', { cache: 'no-store' })
      .then(function (response) {
        if (!response.ok) throw new Error('admin_truth_v2.json unavailable');
        return response.json();
      })
      .then(function (payload) { apply(containerId, payload); })
      .catch(function () { unavailable(containerId); });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();

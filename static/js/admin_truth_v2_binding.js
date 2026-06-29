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

  function formatNumber(value) { return Number(value).toLocaleString(); }
  function badge(status) { return status === 'aligned' ? 'Aligned' : (status || 'Unknown'); }
  function severityClass(severity) {
    if (severity === 'ok') return 'truth-badge--ok';
    if (severity === 'critical') return 'truth-badge--critical';
    return 'truth-badge--warning';
  }

  function sourceLine(payload) {
    var generated = payload && payload.generated_at_utc ? payload.generated_at_utc : 'timestamp unavailable';
    return '<div class="admin-truth-v2-source">Source: Admin Truth Layer v2 snapshot (' + esc(generated) + ')</div>';
  }

  function namedAccessLine(namedPayload, reconPayload) {
    var fpSummary = namedPayload && namedPayload.summary ? namedPayload.summary : {};
    var reconSummary = reconPayload && reconPayload.summary ? reconPayload.summary : {};
    var safe = !!(namedPayload && namedPayload.source_status === 'generated' && namedPayload.safe_to_show_named_access_ui === true)
      || !!(reconPayload && reconPayload.safe_to_enable_named_access_ui === true);
    if (!safe) {
      return {
        css: 'admin-truth-v2-guard admin-truth-v2-guard--blocked',
        html: 'Named user-to-site footprint remains guarded because reconciliation has not passed safe_to_enable_named_access_ui=true.'
      };
    }
    var users = fpSummary.users_analyzed || reconSummary.named_unique_users || 'DATA UNAVAILABLE';
    var assignments = fpSummary.total_product_access_assignments || reconSummary.named_product_access_assignments || 'DATA UNAVAILABLE';
    var api = fpSummary.reconciled_api_product_users || reconSummary.api_product_users || 'DATA UNAVAILABLE';
    var delta = fpSummary.named_minus_api_product;
    if (delta === undefined || delta === null) delta = reconSummary.named_minus_api_product;
    return {
      css: 'admin-truth-v2-guard admin-truth-v2-guard--unlocked',
      html: 'Named access footprint is unlocked: ' + esc(users) + ' named users, ' + esc(assignments) + ' product assignments, reconciled against ' + esc(api) + ' API product users. Named minus API product: ' + esc(delta) + '.'
    };
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
      '<div><h2>' + esc(title) + '</h2><p>' + esc(subtitle) + '</p></div>' +
      '<span id="' + rootId + '-status" class="truth-badge">Loading</span>' +
      '</div>' +
      '<div class="admin-truth-v2-grid">' +
      '<div class="truth-mini"><span>Human users</span><strong id="' + rootId + '-humans">DATA UNAVAILABLE</strong><small>Admin identity truth</small></div>' +
      '<div class="truth-mini"><span>Billing seats</span><strong id="' + rootId + '-billing">DATA UNAVAILABLE</strong><small>Commercial truth</small></div>' +
      '<div class="truth-mini"><span>API product users</span><strong id="' + rootId + '-api">DATA UNAVAILABLE</strong><small>Application role count</small></div>' +
      '<div class="truth-mini"><span>Variance</span><strong id="' + rootId + '-variance">DATA UNAVAILABLE</strong><small>API minus billing</small></div>' +
      '<div class="truth-mini"><span>Ratio</span><strong id="' + rootId + '-ratio">DATA UNAVAILABLE</strong><small>Seats per human</small></div>' +
      '<div class="truth-mini"><span>Confirmed product sites</span><strong id="' + rootId + '-sites">DATA UNAVAILABLE</strong><small>API-visible Jira resources</small></div>' +
      '</div>' +
      '<div id="' + rootId + '-insight" class="admin-truth-v2-insight">Waiting for Admin Truth Layer v2.</div>' +
      '<div id="' + rootId + '-guard" class="admin-truth-v2-guard">Waiting for named access reconciliation.</div>';
    var anchor = root.querySelector('.section-header') || root.firstElementChild;
    if (anchor && anchor.nextSibling) root.insertBefore(card, anchor.nextSibling);
    else root.appendChild(card);
    return card;
  }

  function apply(rootId, payload, namedPayload, reconPayload) {
    var guard = truth();
    var summary = payload && payload.summary ? payload.summary : {};
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
        sitesEl.classList.remove('truth-unavailable');
      }
    }
    var insight = document.getElementById(rootId + '-insight');
    if (insight) insight.innerHTML = esc(summary.interpretation || 'Admin Truth Layer v2 loaded without interpretation.') + sourceLine(payload);
    var named = namedAccessLine(namedPayload, reconPayload);
    var guardText = document.getElementById(rootId + '-guard');
    if (guardText) {
      guardText.className = named.css;
      guardText.innerHTML = named.html;
    }
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

  function getJson(url) {
    return fetch(url, { cache: 'no-store' }).then(function (response) {
      if (!response.ok) return null;
      return response.json();
    }).catch(function () { return null; });
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
    panel(containerId, 'Admin Truth Layer v2', 'Verified comparison between Admin identity, Atlassian billing, Jira API product access, and named access footprint readiness.');
    Promise.all([
      getJson('/static/data/admin_truth_v2.json'),
      getJson('/static/data/user_footprint.json'),
      getJson('/reports/named_access_reconciliation_v2.json')
    ]).then(function (results) {
      if (!results[0]) { unavailable(containerId); return; }
      apply(containerId, results[0], results[1], results[2]);
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();

/* JOM Estate release frontend v1
 * Owner: static/js/jom_estate_lifecycle_v1.js
 * Contract: /api/workspace/estate
 * Rules: no static dataset path, no legacy JSON, no Command Centre contract dependency.
 */
(function () {
  'use strict';

  const CONTRACT_URL = '/api/workspace/estate';

  const asArray = value => Array.isArray(value) ? value : [];
  const asNumber = (value, fallback) => {
    const n = Number(value);
    return Number.isFinite(n) ? n : fallback;
  };
  const unwrap = payload => payload && typeof payload === 'object' && payload.data && typeof payload.data === 'object' ? payload.data : (payload || {});

  function get(obj, path, fallback) {
    let current = obj;
    for (const part of String(path || '').split('.')) {
      if (current && typeof current === 'object' && part in current) current = current[part];
      else return fallback;
    }
    return current === null || current === undefined ? fallback : current;
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function setText(id, value, state) {
    const node = document.getElementById(id);
    if (!node) return;
    node.textContent = value === null || value === undefined || value === '' ? '--' : String(value);
    if (state) node.setAttribute('data-state', state);
  }

  function normaliseState(site) {
    return String(site.lifecycle || site.classification || site.status || site.state || site.collector_onboarding_status || '').toLowerCase();
  }

  function isMonitored(site) {
    const state = normaliseState(site);
    return !!(site.is_monitored === true || site.monitored === true || site.in_monitoring_scope === true || state === 'monitored' || state.includes('monitoring_enabled') || state.includes('monitoring enabled'));
  }

  function isIgnored(site) {
    const state = normaliseState(site);
    return state.includes('ignored') || state.includes('retired');
  }

  function needsReview(site) {
    if (!site || isMonitored(site) || isIgnored(site)) return false;
    const state = normaliseState(site);
    return state === '' || state.includes('discovered') || state.includes('review') || state.includes('pending') || state.includes('gap') || state.includes('error');
  }

  function siteKey(site) {
    return String(site.site_key || site.key || site.cloud_id || site.name || site.site_name || '').trim();
  }

  function siteName(site) {
    return String(site.name || site.site_name || site.key || site.site_key || 'Unknown site');
  }

  function siteUrl(site) {
    return String(site.url || site.site_url || '').trim();
  }

  function lifecycleLabel(site) {
    if (isMonitored(site)) return 'Monitored';
    if (isIgnored(site)) return 'Ignored';
    const state = normaliseState(site);
    if (state.includes('pending')) return 'Approval Pending';
    if (state.includes('error') || state.includes('gap')) return 'Review Required';
    if (state.includes('review')) return 'Review Required';
    return 'Discovered';
  }

  function healthLabel(site) {
    if (isMonitored(site)) return 'Healthy';
    if (isIgnored(site)) return 'Ignored';
    return 'Review';
  }

  function pillClass(label) {
    const value = String(label || '').toLowerCase();
    if (value.includes('healthy') || value.includes('monitored') || value === 'ok') return 'estate-status-pill estate-status-pill--ok';
    if (value.includes('ignored') || value.includes('retired')) return 'estate-status-pill estate-status-pill--retired';
    return 'estate-status-pill estate-status-pill--review';
  }

  function sitesFromPayload(root) {
    const candidates = [
      get(root, 'registry.sites', null),
      get(root, 'site_registry.sites', null),
      get(root, 'sites', null),
      get(root, 'registry.items', null)
    ];
    for (const list of candidates) {
      if (Array.isArray(list)) return list.filter(item => item && typeof item === 'object');
    }
    return [];
  }

  function summaryFromPayload(root, sites) {
    const summary = get(root, 'registry_summary', get(root, 'registry.summary', get(root, 'summary', {}))) || {};
    const metrics = get(root, 'metrics', {}) || {};
    const total = asNumber(summary.total_sites ?? summary.site_count ?? metrics.total_sites, sites.length);
    const monitored = asNumber(summary.monitored_count ?? metrics.monitored_sites, sites.filter(isMonitored).length);
    const discovered = asNumber(summary.discovered_count ?? metrics.discovered_sites, sites.filter(needsReview).length);
    const pending = asNumber(summary.pending_onboarding_count ?? summary.pending_count ?? metrics.pending_onboarding, sites.filter(site => normaliseState(site).includes('pending')).length);
    const review = asNumber(summary.review_count ?? metrics.review_items, sites.filter(needsReview).length);
    const ignored = sites.filter(isIgnored).length;
    const coverage = total > 0 ? Math.round((monitored / total) * 100) : 0;
    return {total, monitored, discovered, pending, review, ignored, coverage};
  }

  function userCount(root) {
    const candidates = [
      get(root, 'users.metric', null),
      get(root, 'users_metric.metric', null),
      get(root, 'estate_product_access.summary.total_jira_product_user_count', null),
      get(root, 'users.summary.total_jira_product_user_count', null)
    ];
    for (const value of candidates) {
      const n = asNumber(value, null);
      if (n !== null) return n;
    }
    return null;
  }

  function renderReviewQueue(sites, summary) {
    const list = document.getElementById('estate-review-list');
    const count = document.getElementById('estate-review-count');
    const reviewSites = sites.filter(needsReview);
    setText('estate-review-count', reviewSites.length);
    if (!list) return;
    if (!reviewSites.length) {
      list.innerHTML = '<p class="estate-empty">No discovered sites currently require lifecycle review.</p>';
      return;
    }
    list.innerHTML = reviewSites.map(site => {
      const key = siteKey(site);
      const name = siteName(site);
      const reason = lifecycleLabel(site);
      const url = siteUrl(site);
      const action = url ? '<a class="estate-action-link" href="' + escapeHtml(url) + '" target="_blank" rel="noopener noreferrer">Open site</a>' : '<span class="estate-status-pill estate-status-pill--review">Review required</span>';
      return '<article class="estate-review-item">' +
        '<div><strong>' + escapeHtml(name) + '</strong><br><small>Key: ' + escapeHtml(key || 'Unavailable') + '</small><br><span>' + escapeHtml(reason) + '</span></div>' +
        action +
      '</article>';
    }).join('');
  }

  function renderRegistry(sites) {
    const body = document.getElementById('estate-registry-body');
    if (!body) return;
    if (!sites.length) {
      body.innerHTML = '<tr><td colspan="6">No site records were returned by the live Estate contract.</td></tr>';
      return;
    }
    const sorted = sites.slice().sort((a, b) => {
      const ma = isMonitored(a) ? 0 : 1;
      const mb = isMonitored(b) ? 0 : 1;
      if (ma !== mb) return ma - mb;
      return siteName(a).localeCompare(siteName(b));
    });
    body.innerHTML = sorted.map(site => {
      const key = siteKey(site);
      const name = siteName(site);
      const url = siteUrl(site);
      const lifecycle = lifecycleLabel(site);
      const monitoring = isMonitored(site) ? 'Enabled' : 'Not enabled';
      const health = healthLabel(site);
      const last = site.last_observation || site.last_seen || site.observed_at || site.updated_at || 'Live contract';
      const action = url ? '<a class="estate-site-link estate-site-link--button" href="' + escapeHtml(url) + '" target="_blank" rel="noopener noreferrer">Open site <span class="estate-external-icon">â†—</span></a>' : '<span class="estate-status-pill estate-status-pill--review">No site link</span>';
      return '<tr data-site-key="' + escapeHtml(key) + '" data-estate-state="' + escapeHtml(normaliseState(site)) + '">' +
        '<td><strong>' + escapeHtml(name) + '</strong><br><small>' + escapeHtml(key || 'Unavailable') + '</small></td>' +
        '<td><span class="' + pillClass(lifecycle) + '">' + escapeHtml(lifecycle) + '</span></td>' +
        '<td><span class="' + pillClass(monitoring) + '">' + escapeHtml(monitoring) + '</span></td>' +
        '<td><span class="' + pillClass(health) + '">' + escapeHtml(health) + '</span></td>' +
        '<td>' + escapeHtml(last) + '</td>' +
        '<td>' + action + '</td>' +
      '</tr>';
    }).join('');
  }

  function updateRail(root, sites, summary) {
    setText('rail-total-sites', summary.total);
    setText('rail-monitored-sites', summary.monitored);
    setText('rail-discovered-sites', summary.discovered);
    setText('rail-review-queue', summary.review);
    setText('rail-pending-sites', summary.pending);
    setText('rail-ignored-sites', summary.ignored);
    setText('rail-registry-status', sites.length ? 'OK' : 'Review', sites.length ? 'ok' : 'review');
    setText('rail-users-count', userCount(root) === null ? '--' : userCount(root));
    setText('rail-alert-count', summary.review);
  }

  function applyFiltering() {
    const search = document.getElementById('estate-search');
    const filter = document.getElementById('estate-filter');
    const rows = Array.from(document.querySelectorAll('#estate-registry-body tr'));
    const term = String(search && search.value || '').toLowerCase();
    const mode = String(filter && filter.value || 'all').toLowerCase();
    rows.forEach(row => {
      const text = row.textContent.toLowerCase();
      const state = String(row.getAttribute('data-estate-state') || '').toLowerCase();
      let match = !term || text.includes(term);
      if (mode === 'monitored') match = match && text.includes('enabled');
      if (mode === 'discovered') match = match && !text.includes('enabled') && !state.includes('ignored');
      if (mode === 'pending') match = match && state.includes('pending');
      if (mode === 'ignored') match = match && state.includes('ignored');
      row.style.display = match ? '' : 'none';
    });
  }

  function bindFilters() {
    const search = document.getElementById('estate-search');
    const filter = document.getElementById('estate-filter');
    if (search && !search.dataset.jomBound) {
      search.dataset.jomBound = 'true';
      search.addEventListener('input', applyFiltering);
    }
    if (filter && !filter.dataset.jomBound) {
      filter.dataset.jomBound = 'true';
      filter.addEventListener('change', applyFiltering);
    }
  }

  function render(payload) {
    const root = unwrap(payload);
    const sites = sitesFromPayload(root);
    const summary = summaryFromPayload(root, sites);
    renderReviewQueue(sites, summary);
    renderRegistry(sites);
    updateRail(root, sites, summary);
    bindFilters();
  }

  function renderError(error) {
    const review = document.getElementById('estate-review-list');
    const body = document.getElementById('estate-registry-body');
    if (review) review.innerHTML = '<p class="estate-empty">Estate workspace contract could not be loaded.</p>';
    if (body) body.innerHTML = '<tr><td colspan="6">Estate workspace contract could not be loaded: ' + escapeHtml(error && error.message ? error.message : error) + '</td></tr>';
    setText('rail-registry-status', 'Review', 'review');
  }

  function loadEstate() {
    fetch(CONTRACT_URL, {cache: 'no-store', headers: {'Accept': 'application/json'}, credentials: 'same-origin'})
      .then(response => {
        if (!response.ok) throw new Error('Estate workspace contract returned HTTP ' + response.status);
        return response.json();
      })
      .then(render)
      .catch(renderError);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', loadEstate);
  else loadEstate();
}());

// JOM Estate Existing UI Filter Patch v1 START
(function () {
  "use strict";

  const CONTRACT_URL = "/api/workspace/estate";
  const LIVE_EVIDENCE = new Set([
    "live_oauth_accessible_resources",
    "live_admin_event_reference",
    "live_admin_org",
    "live_product_access",
    "oauth_accessible_resources",
    "admin_org_events"
  ]);
  const UNTRUSTED_EVIDENCE = new Set([
    "manual_unverified",
    "manual_validation_target",
    "known_from_support_case_manual_only",
    "known_from_admin_screenshot_or_support_case_manual_only",
    "static",
    "cached",
    "unknown"
  ]);

  function asArray(value) {
    return Array.isArray(value) ? value : [];
  }

  function lower(value) {
    return String(value || "").toLowerCase();
  }

  function normalizeKey(value) {
    return lower(value).replace(/^https?:\/\//, "").replace(/\.atlassian\.net.*$/, "").trim();
  }

  function getRecordKey(record) {
    const inventory = record.inventory || {};
    const registry = record.registry || {};
    return normalizeKey(
      record.key ||
      record.site_key ||
      record.siteKey ||
      record.name ||
      record.site_name ||
      registry.site_key ||
      registry.siteKey ||
      registry.site_name ||
      inventory.site_key ||
      inventory.siteKey ||
      inventory.name ||
      inventory.url ||
      record.url ||
      ""
    );
  }

  function mergedSignals(record) {
    const inventory = record.inventory || {};
    const registry = record.registry || {};
    return {
      key: getRecordKey(record),
      sources: [
        ...asArray(record.sources),
        ...asArray(record.source),
        ...asArray(inventory.sources),
        ...asArray(registry.sources)
      ].map(lower),
      evidence: [
        ...asArray(record.evidence_levels),
        ...asArray(record.evidenceLevels),
        ...asArray(inventory.evidence_levels),
        ...asArray(registry.evidence_levels)
      ].map(lower),
      lifecycle: lower(record.lifecycle || registry.lifecycle || inventory.lifecycle || registry.collector_onboarding_status || inventory.collector_onboarding_status || record.status || registry.status || inventory.status),
      approvedMonitored: record.approved_monitored === true || registry.approved_monitored === true || inventory.approved_monitored === true,
      monitored: record.is_monitored === true || record.monitored === true || registry.is_monitored === true || registry.monitored === true || inventory.is_monitored === true || inventory.monitored === true
    };
  }

  function hasLiveEvidence(signals) {
    const values = [...signals.sources, ...signals.evidence];
    return values.some((value) => LIVE_EVIDENCE.has(value));
  }

  function isManualOnly(signals) {
    const values = [...signals.sources, ...signals.evidence];
    return values.length > 0 && values.every((value) => UNTRUSTED_EVIDENCE.has(value));
  }

  function isDeletion(signals) {
    return signals.lifecycle.includes("deletion") || signals.lifecycle.includes("deleted") || signals.lifecycle.includes("retired") || signals.lifecycle.includes("archive");
  }

  function collectRecords(contract) {
    const data = contract && contract.data ? contract.data : contract || {};
    const rows = [];

    asArray(contract && contract.sites).forEach((row) => rows.push(row));
    asArray(contract && contract.registry && contract.registry.sites).forEach((row) => rows.push(row));
    asArray(data.registry && data.registry.sites).forEach((row) => rows.push(row));
    asArray(contract && contract.inventory && contract.inventory.sites).forEach((row) => rows.push({ inventory: row, key: row.site_key, name: row.name || row.site_key, url: row.url }));
    asArray(data.estate_admin_site_inventory && data.estate_admin_site_inventory.sites).forEach((row) => rows.push({ inventory: row, key: row.site_key, name: row.name || row.site_key, url: row.url }));

    return rows;
  }

  function buildModel(contract) {
    const byKey = new Map();
    collectRecords(contract).forEach((row) => {
      const signals = mergedSignals(row);
      if (!signals.key) return;
      const current = byKey.get(signals.key) || {
        key: signals.key,
        live: false,
        manualOnly: true,
        monitored: false,
        deletion: false
      };
      current.live = current.live || hasLiveEvidence(signals);
      current.manualOnly = current.manualOnly && isManualOnly(signals);
      current.monitored = current.monitored || signals.approvedMonitored || signals.monitored || signals.lifecycle === "monitored";
      current.deletion = current.deletion || isDeletion(signals);
      byKey.set(signals.key, current);
    });

    const model = {
      monitored: new Set(),
      discovery: new Set(),
      deletion: new Set(),
      excluded: new Set()
    };

    byKey.forEach((record, key) => {
      if (!record.live || record.manualOnly) {
        model.excluded.add(key);
      } else if (record.deletion) {
        model.deletion.add(key);
      } else if (record.monitored) {
        model.monitored.add(key);
      } else {
        model.discovery.add(key);
      }
    });

    return model;
  }

  function findKeyInText(text) {
    const value = lower(text || "");
    const keyMatch = value.match(/key:\s*([a-z0-9][a-z0-9-]+)/);
    if (keyMatch) return normalizeKey(keyMatch[1]);
    const urlMatch = value.match(/https?:\/\/([a-z0-9-]+)\.atlassian\.net/);
    if (urlMatch) return normalizeKey(urlMatch[1]);
    return "";
  }

  function nearestSectionLabel(element) {
    let node = element;
    for (let depth = 0; node && depth < 8; depth += 1, node = node.parentElement) {
      const text = lower(node.innerText || "");
      if (text.includes("discovery review queue") || text.includes("discovery queue")) return "discovery";
      if (text.includes("site registry") || text.includes("central inventory")) return "registry";
      if (text.includes("deletion") || text.includes("lifecycle queue")) return "deletion";
    }
    return "unknown";
  }

  function candidateRows() {
    return Array.from(document.querySelectorAll("article, tr, li, .site-row, .site-card, .queue-item, .registry-row, .jom-card, .jom-table-row"));
  }

  function shouldRemoveRow(section, key, model) {
    if (!key) return false;
    if (model.excluded.has(key)) return true;
    if (section === "registry" && !model.monitored.has(key)) return true;
    if (section === "discovery" && !model.discovery.has(key)) return true;
    if (section === "deletion" && !model.deletion.has(key)) return true;
    return false;
  }

  function removeRows(model) {
    candidateRows().forEach((row) => {
      const key = findKeyInText(row.innerText || row.textContent || "");
      const section = nearestSectionLabel(row);
      if (shouldRemoveRow(section, key, model)) {
        row.setAttribute("data-jom-estate-filtered", "true");
        row.remove();
      }
    });
  }

  function updateVisibleCounts(model) {
    const map = [
      { label: "total sites", value: model.monitored.size + model.discovery.size + model.deletion.size },
      { label: "monitored", value: model.monitored.size },
      { label: "discovered", value: model.discovery.size },
      { label: "review queue", value: model.discovery.size },
      { label: "approval pending", value: model.discovery.size },
      { label: "ignored", value: 0 }
    ];

    Array.from(document.querySelectorAll("*"))
      .filter((el) => el.children.length === 0 && /^\d+$/.test((el.textContent || "").trim()))
      .forEach((el) => {
        const parentText = lower((el.parentElement && el.parentElement.innerText) || "");
        const found = map.find((item) => parentText.includes(item.label));
        if (found) el.textContent = String(found.value);
      });
  }

  function applyEstateDisplayFilter(model) {
    removeRows(model);
    updateVisibleCounts(model);
    window.JOMEstateDisplayFilterV1 = {
      monitored: Array.from(model.monitored),
      discovery: Array.from(model.discovery),
      deletion: Array.from(model.deletion),
      excluded: Array.from(model.excluded)
    };
  }

  async function runFilter() {
    try {
      const response = await fetch(CONTRACT_URL, { headers: { "Accept": "application/json" } });
      if (!response.ok) return;
      const contract = await response.json();
      const model = buildModel(contract);

      let attempts = 0;
      const timer = window.setInterval(() => {
        attempts += 1;
        applyEstateDisplayFilter(model);
        if (attempts >= 10) window.clearInterval(timer);
      }, 250);
    } catch (error) {
      console.warn("JOM Estate display filter skipped", error);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", runFilter);
  } else {
    runFilter();
  }
}());
// JOM Estate Existing UI Filter Patch v1 END

// JOM Estate Registry Table Filter Fix v1 START
(function(){
  "use strict";
  const CONTRACT_URL="/api/workspace/estate";
  const LIVE=new Set(["live_oauth_accessible_resources","live_admin_event_reference","oauth_accessible_resources","admin_org_events","live_admin_org","live_product_access"]);
  const BAD=new Set(["manual_unverified","manual_validation_target","known_from_support_case_manual_only","known_from_admin_screenshot_or_support_case_manual_only","static","cached","unknown"]);
  function arr(v){return Array.isArray(v)?v:[];}
  function low(v){return String(v||"").toLowerCase();}
  function norm(v){return low(v).replace(/^https?:\/\//,"").replace(/\.atlassian\.net.*$/,"").trim();}
  function keyOf(r){const i=r.inventory||{},g=r.registry||{};return norm(r.key||r.site_key||r.siteKey||r.name||r.site_name||g.site_key||g.siteKey||g.site_name||i.site_key||i.siteKey||i.name||i.url||r.url||"");}
  function sig(r){const i=r.inventory||{},g=r.registry||{};return {key:keyOf(r),src:[...arr(r.sources),...arr(i.sources),...arr(g.sources)].map(low),ev:[...arr(r.evidence_levels),...arr(i.evidence_levels),...arr(g.evidence_levels)].map(low),mon:r.approved_monitored===true||g.approved_monitored===true||i.approved_monitored===true||r.is_monitored===true||r.monitored===true||g.is_monitored===true||g.monitored===true||i.is_monitored===true||i.monitored===true||low(r.lifecycle||g.lifecycle||i.lifecycle)==="monitored"};}
  function live(s){return [...s.src,...s.ev].some(v=>LIVE.has(v));}
  function manualOnly(s){const vals=[...s.src,...s.ev];return vals.length>0&&vals.every(v=>BAD.has(v));}
  function rows(c){const d=c&&c.data?c.data:c||{},out=[]; arr(c&&c.sites).forEach(x=>out.push(x)); arr(c&&c.registry&&c.registry.sites).forEach(x=>out.push(x)); arr(d.registry&&d.registry.sites).forEach(x=>out.push(x)); arr(c&&c.inventory&&c.inventory.sites).forEach(x=>out.push({inventory:x,key:x.site_key,name:x.name||x.site_key,url:x.url})); arr(d.estate_admin_site_inventory&&d.estate_admin_site_inventory.sites).forEach(x=>out.push({inventory:x,key:x.site_key,name:x.name||x.site_key,url:x.url})); return out;}
  function model(c){const m={mon:new Set(),disc:new Set(),excluded:new Set()}; rows(c).forEach(r=>{const s=sig(r); if(!s.key)return; if(!live(s)||manualOnly(s))m.excluded.add(s.key); else if(s.mon)m.mon.add(s.key); else m.disc.add(s.key);}); return m;}
  function keyFromRow(tr){const txt=low(tr.innerText||tr.textContent||""); let m=txt.match(/key:\s*([a-z0-9][a-z0-9-]+)/); if(m)return norm(m[1]); m=txt.match(/^\s*([a-z0-9][a-z0-9-]+)\s+\1\s+/); if(m)return norm(m[1]); const first=(tr.querySelector("td,th")||{}).innerText||""; const lines=first.split(/\n|\r/).map(x=>x.trim()).filter(Boolean); return norm(lines[0]||"");}
  function findRegistryTables(){return Array.from(document.querySelectorAll("table")).filter(t=>low((t.closest("section,main,div")||t).innerText).includes("site registry")||low(t.innerText).includes("last observation"));}
  function filterRegistryTable(m){findRegistryTables().forEach(table=>{Array.from(table.querySelectorAll("tbody tr, tr")).forEach(tr=>{if(tr.querySelector("th"))return; const k=keyFromRow(tr); if(!k)return; if(m.excluded.has(k)||!m.mon.has(k)){tr.remove();}});});}
  function updateCounts(m){Array.from(document.querySelectorAll("*"))
    .filter(e=>e.children.length===0&&/^\d+$/.test((e.textContent||"").trim()))
    .forEach(e=>{const p=low((e.parentElement&&e.parentElement.innerText)||""); if(p.includes("total sites"))e.textContent=String(m.mon.size+m.disc.size); else if(p.includes("monitored"))e.textContent=String(m.mon.size); else if(p.includes("discovered"))e.textContent=String(m.disc.size); else if(p.includes("review queue"))e.textContent=String(m.disc.size);});}
  async function run(){try{const r=await fetch(CONTRACT_URL,{headers:{Accept:"application/json"}}); if(!r.ok)return; const c=await r.json(); const m=model(c); let n=0; const timer=setInterval(()=>{n++; filterRegistryTable(m); updateCounts(m); window.JOMEstateRegistryTableFilterFixV1={monitored:[...m.mon],discovery:[...m.disc],excluded:[...m.excluded]}; if(n>=12)clearInterval(timer);},250);}catch(e){console.warn("JOM registry table filter skipped",e);}}
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",run); else run();
}());
// JOM Estate Registry Table Filter Fix v1 END


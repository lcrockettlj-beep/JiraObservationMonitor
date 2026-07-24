(function(){
  'use strict';

  const ENDPOINT = '/api/workspace/command-centre';

  function unwrap(payload){
    if(payload && typeof payload === 'object' && payload.data && typeof payload.data === 'object') return payload.data;
    return payload || {};
  }

  function get(obj, path, fallback){
    let cur = obj;
    for(const part of path.split('.')){
      if(cur && typeof cur === 'object' && part in cur) cur = cur[part];
      else return fallback;
    }
    return cur === undefined || cur === null ? fallback : cur;
  }

  function asNumber(value, fallback){
    const n = Number(value);
    return Number.isFinite(n) ? n : fallback;
  }

  function asArray(value){ return Array.isArray(value) ? value : []; }

  function setText(id, value){
    const el = document.getElementById(id);
    if(!el) return;
    el.textContent = value === null || value === undefined || value === '' ? 'n/a' : String(value);
  }

  function setHtml(id, html){
    const el = document.getElementById(id);
    if(el) el.innerHTML = html;
  }

  function escapeHtml(value){
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  async function loadWorkspace(){
    const response = await fetch(ENDPOINT, { cache: 'no-store' });
    if(!response.ok) throw new Error(ENDPOINT + ' returned ' + response.status);
    return unwrap(await response.json());
  }

  function siteState(site){
    return String(site && (site.classification || site.status || site.state || site.monitoring_state || site.collector_onboarding_status) || '').toLowerCase();
  }

  function isMonitored(site){
    const state = siteState(site);
    return !!(site && (site.is_monitored === true || site.monitored === true || site.in_monitoring_scope === true || state === 'monitored' || state.includes('monitoring enabled')));
  }

  function isDiscovered(site){
    const state = siteState(site);
    return !!(site && !isMonitored(site) && !state.includes('ignored') && !state.includes('retired'));
  }

  function deriveRegistry(root){
    const registry = unwrap(get(root, 'registry', get(root, 'site_registry', {})));
    const sites = asArray(registry.sites || get(root, 'sites', []));
    const summary = get(root, 'registry_summary', get(registry, 'summary', get(root, 'summary', {}))) || {};
    const total = asNumber(summary.total_sites ?? summary.site_count, sites.length);
    const monitored = asNumber(summary.monitored_count, sites.filter(isMonitored).length);
    const discovered = asNumber(summary.discovered_count, sites.filter(isDiscovered).length);
    const pending = asNumber(summary.pending_onboarding_count ?? summary.pending_count, sites.filter(site => siteState(site).includes('pending')).length);
    const review = Math.max(discovered, pending, 0);
    const coverage = total > 0 ? Math.round((monitored / total) * 100) : 0;
    return { total, monitored, discovered, pending, review, coverage, sites };
  }

  function deriveUsers(root){
    const candidates = [
      get(root, 'users.metric', null),
      get(root, 'users_metric', null),
      get(root, 'users_metric.metric', null),
      get(root, 'users.summary.total_product_access_assignments', null),
      get(root, 'users.summary.total_jira_product_user_count', null),
      get(root, 'live_product_access.total_jira_product_user_count', null),
      get(root, 'product_access.summary.total_jira_product_user_count', null),
      get(root, 'estate_product_access.summary.total_jira_product_user_count', null)
    ];
    for(const value of candidates){
      const n = asNumber(value, null);
      if(n !== null) return n;
    }
    return null;
  }

  function deriveRuntime(root){
    const value = String(get(root, 'operator_summary.runtime.last_result_status', get(root, 'operator_summary.runtime.state', get(root, 'runtime.state', 'ok'))) || '').toLowerCase();
    if(value.includes('fail') || value.includes('error') || value.includes('critical')) return 'Review';
    if(value.includes('running')) return 'Running';
    return 'OK';
  }

  function actionKey(action){
    const title = String(action.title || action.message || '').toLowerCase();
    const source = String(action.source || action.category || '').toLowerCase();
    if(title.includes('discovered') || source.includes('site_registry')) return 'discovered-sites';
    if(title.includes('admin truth') || source.includes('admin_truth')) return 'admin-truth';
    return title + '|' + source;
  }

  function actionHref(action){
    const key = actionKey(action);
    if(key === 'discovered-sites') return '/estate#site-registry';
    if(key === 'admin-truth') return '/reference';
    const source = String(action.source || action.category || '').toLowerCase();
    if(source.includes('runtime') || source.includes('operator')) return '/operator/observability';
    return '/estate';
  }

  function actionButtonLabel(action){
    const key = actionKey(action);
    if(key === 'discovered-sites') return 'Open Estate review';
    if(key === 'admin-truth') return 'Open Admin';
    const source = String(action.source || action.category || '').toLowerCase();
    if(source.includes('runtime') || source.includes('operator')) return 'Open Runtime Status';
    return 'Open workspace';
  }

  function deriveActions(root){
    const out = [];
    const direct = asArray(get(root, 'operator_alerts.alerts', []));
    const summaryAlerts = asArray(get(root, 'operator_summary.top_alerts', []));
    const rawAlerts = asArray(get(root, 'alerts', []));
    out.push(...direct, ...summaryAlerts, ...rawAlerts);

    const registry = deriveRegistry(root);
    const hasDiscovered = out.some(item => actionKey(item) === 'discovered-sites');
    if(registry.discovered > 0 && !hasDiscovered){
      out.push({
        level: 'review',
        title: 'Discovered sites need classification',
        impact: registry.discovered + ' discovered site' + (registry.discovered === 1 ? '' : 's') + ' need a monitoring decision.',
        action: 'Open Estate and classify each discovered site as monitored, pending, ignored, or review.',
        source: 'Site Registry'
      });
    }

    const adminTruthWarning = get(root, 'admin_truth.warning', get(root, 'admin_truth_warnings.0', null));
    const hasAdminTruth = out.some(item => actionKey(item) === 'admin-truth');
    if(adminTruthWarning && !hasAdminTruth){
      out.push({
        level: 'warning',
        title: 'Admin truth requires review',
        impact: typeof adminTruthWarning === 'string' ? adminTruthWarning : 'Admin truth has a warning that should be reviewed.',
        action: 'Refresh or review Admin Truth before stakeholder reporting.',
        source: 'Admin Truth'
      });
    }

    const seen = new Set();
    return out.filter(item => {
      if(!item || typeof item !== 'object') return false;
      const key = actionKey(item);
      if(seen.has(key)) return false;
      seen.add(key);
      return true;
    }).slice(0, 6);
  }

  function normaliseAction(alert){
    const key = actionKey(alert);
    if(key === 'discovered-sites'){
      const registry = null;
      return {
        level: String(alert.level || 'review').toLowerCase(),
        title: 'Discovered sites need classification',
        impact: String(alert.impact || alert.reason || 'One or more discovered sites are not yet monitored.'),
        action: String(alert.action || alert.recommended_action || 'Review site registry and onboarding decisions.'),
        source: String(alert.source || 'Site Registry'),
        href: actionHref(alert),
        button: actionButtonLabel(alert)
      };
    }
    return {
      level: String(alert.level || alert.severity || 'review').toLowerCase(),
      title: String(alert.title || alert.message || 'Action required'),
      impact: String(alert.impact || alert.reason || alert.description || 'This item needs review.'),
      action: String(alert.action || alert.recommended_action || 'Review the related workspace and confirm the next action.'),
      source: String(alert.source || alert.category || 'JOM'),
      href: actionHref(alert),
      button: actionButtonLabel(alert)
    };
  }

  function renderCoverage(root){
    const registry = deriveRegistry(root);
    const ring = document.querySelector('.jom-coverage-ring');
    if(ring) ring.style.setProperty('--coverage-deg', Math.max(0, Math.min(360, registry.coverage * 3.6)) + 'deg');
    const monitoredBar = document.getElementById('jom-rail-coverage-monitored');
    const reviewBar = document.getElementById('jom-rail-coverage-review');
    if(monitoredBar) monitoredBar.style.width = Math.max(0, Math.min(100, registry.coverage)) + '%';
    if(reviewBar) reviewBar.style.width = Math.max(0, Math.min(100, 100 - registry.coverage)) + '%';
    setText('jom-rail-monitoring-coverage', registry.coverage + '%');
    setText('jom-rail-coverage-reason', registry.monitored + '/' + registry.total + ' sites monitored');
    setText('jom-rail-total-sites', registry.total);
    setText('jom-rail-monitored-sites', registry.monitored);
    setText('jom-rail-review-items', registry.review);
  }

  function renderOperational(root){
    const registry = deriveRegistry(root);
    const users = deriveUsers(root);
    const actions = deriveActions(root);
    setText('jom-rail-data-health', registry.total > 0 && users !== null ? 'OK' : 'Review');
    setText('jom-rail-runtime', deriveRuntime(root));
    setText('jom-rail-alerts', actions.length);
    setText('jom-rail-users', users === null ? 'n/a' : users);
  }

  function renderActions(root){
    const actions = deriveActions(root);
    if(!actions.length){
      setHtml('jom-final-risk-list', '<div class="jom-final-empty">No immediate actions found.</div>');
      return;
    }
    const html = actions.map(alert => {
      const item = normaliseAction(alert);
      const pillClass = 'jom-risk-pill jom-risk-pill--' + escapeHtml(item.level);
      return '<article class="jom-final-risk-card">'
        + '<span class="' + pillClass + '">' + escapeHtml(item.level) + '</span>'
        + '<h3>' + escapeHtml(item.title) + '</h3>'
        + '<p><strong>Impact:</strong> ' + escapeHtml(item.impact) + '</p>'
        + '<p><strong>Recommended action:</strong> ' + escapeHtml(item.action) + '</p>'
        + '<p><strong>Source:</strong> ' + escapeHtml(item.source) + '</p>'
        + '<div class="jom-final-action-row"><a class="jom-final-action" href="' + escapeHtml(item.href) + '">' + escapeHtml(item.button) + '</a></div>'
        + '</article>';
    }).join('');
    setHtml('jom-final-risk-list', html);
  }

  function render(root){
    renderCoverage(root);
    renderOperational(root);
    renderActions(root);
  }

  function renderUnavailable(message){
    setText('jom-rail-monitoring-coverage', 'n/a');
    setText('jom-rail-total-sites', 'n/a');
    setText('jom-rail-monitored-sites', 'n/a');
    setText('jom-rail-review-items', 'n/a');
    setText('jom-rail-data-health', 'Review');
    setText('jom-rail-runtime', 'Review');
    setText('jom-rail-alerts', 'n/a');
    setText('jom-rail-users', 'n/a');
    setHtml('jom-final-risk-list', '<div class="jom-final-empty">Command Centre data is temporarily unavailable. ' + escapeHtml(message || '') + '</div>');
  }

  function boot(){
    loadWorkspace().then(render).catch(error => {
      console.warn('Command Centre workspace renderer failed', error);
      renderUnavailable(error && error.message);
    });
  }

  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();

(function(){
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const arr = value => Array.isArray(value) ? value : [];
  const set = (id, value) => { const el = $(id); if(el) el.textContent = value === undefined || value === null || value === '' ? '--' : String(value); };
  async function json(path){ const res = await fetch(path,{cache:'no-store'}); if(!res.ok) throw new Error(path + ' returned ' + res.status); return res.json(); }
  function siteKey(site){ return String(site.site_key || site.key || site.name || site.url || 'unknown-site').replace(/^https?:\/\//,'').replace(/\.atlassian\.net.*$/,'').split('/')[0].toLowerCase(); }
  function isMonitored(site){ const value = String(site.classification || site.state || site.status || '').toLowerCase(); return value === 'monitored' || site.monitored === true; }
  function registrySites(registry){ return arr(registry.sites); }
  function userSummary(footprint){ const s = footprint.summary || {}; return { users: s.users_analyzed ?? arr(footprint.users).length, named: s.named_unique_users ?? '--', assignments: s.total_product_access_assignments ?? '--', safe: footprint.safe_to_show_named_access_ui ?? footprint.source_status ?? 'unknown' }; }
  function statusPill(text, type){ return '<span class="admin-gov-pill admin-gov-pill--' + type + '">' + esc(text) + '</span>'; }
  function renderDiscovery(registry){ const body = $('admin-gov-discovery-table'); if(!body) return; const discovered = registrySites(registry).filter(site => !isMonitored(site)); set('admin-gov-discovery-count', discovered.length); if(!discovered.length){ body.innerHTML = '<tr><td colspan="3">No unmonitored/discovered sites are currently awaiting review.</td></tr>'; return; } body.innerHTML = discovered.map(site => '<tr><td><strong>'+esc(siteKey(site))+'</strong></td><td>'+statusPill('Review','review')+'</td><td>'+esc(site.url || site.site_url || site.cloud_id || site.source || 'No URL listed')+'</td></tr>').join(''); }
  function renderAccess(footprint){ const target = $('admin-gov-access-list'); if(!target) return; const s = userSummary(footprint); set('admin-gov-users-analysed', s.users); set('admin-gov-access-assignments', s.assignments); target.innerHTML = [
    ['Users analysed', s.users, 'info'],
    ['Named unique users', s.named, 'info'],
    ['Product access assignments', s.assignments, 'info'],
    ['Named access UI state', s.safe, String(s.safe).toLowerCase().includes('safe') ? 'ok' : 'review']
  ].map(([label,value,type]) => '<li><span>'+esc(label)+'</span>'+statusPill(value,type)+'</li>').join(''); }
  function renderProduct(adminTruth, productAccess){ const target = $('admin-gov-product-list'); if(!target) return; const billing = adminTruth.billing_truth || {}; const product = adminTruth.product_access_truth || {}; const productSummary = productAccess.summary || {}; target.innerHTML = [
    ['Billing truth fields', Object.keys(billing).length, Object.keys(billing).length ? 'ok' : 'review'],
    ['Product access truth fields', Object.keys(product).length, Object.keys(product).length ? 'ok' : 'review'],
    ['Product access sites', productSummary.site_count ?? productSummary.sites ?? arr(productAccess.sites).length, 'info'],
    ['Product access errors', arr(productAccess.errors).length || 0, arr(productAccess.errors).length ? 'review' : 'ok']
  ].map(([label,value,type]) => '<li><span>'+esc(label)+'</span>'+statusPill(value,type)+'</li>').join(''); }
  function renderRuntime(summary, observability, sourceState){ const target = $('admin-gov-runtime-list'); if(!target) return; const runtime = summary.runtime || {}; const sourceReliability = sourceState.source_reliability || {}; const freshness = sourceState.source_freshness || {}; const status = runtime.last_result_status || runtime.status || runtime.state || 'unknown'; target.innerHTML = [
    ['Runtime status', status, /ok|healthy|success/i.test(status) ? 'ok' : 'review'],
    ['Last finished', runtime.last_finished_at_utc || '--', 'info'],
    ['Runtime history', arr(observability.runtime_history).length, 'info'],
    ['Source reliability', sourceReliability.status || sourceReliability.overall_status || 'available', 'info'],
    ['Source freshness keys', Object.keys(freshness).length, Object.keys(freshness).length ? 'ok' : 'review']
  ].map(([label,value,type]) => '<li><span>'+esc(label)+'</span>'+statusPill(value,type)+'</li>').join(''); }
  function renderActions(registry, footprint, sourceState){ const target = $('admin-gov-action-list'); if(!target) return; const discovered = registrySites(registry).filter(site => !isMonitored(site)).length; const users = userSummary(footprint); const actions = [];
    if(discovered) actions.push('Review ' + discovered + ' discovered/unmonitored site(s) and decide whether to monitor, ignore or investigate.');
    if(String(users.safe).toLowerCase().includes('safe')) actions.push('Named access surface is safe to review; continue access governance validation.');
    else actions.push('Review named access source status before expanding access-governance actions.');
    if(sourceState.source_reliability) actions.push('Check source reliability/freshness before stakeholder demo or export run.');
    actions.push('Keep retained /api compatibility routes until backend contract deprecation is formally planned.');
    target.innerHTML = actions.map(a => '<li>'+esc(a)+'</li>').join('');
  }
  function setPosture(registry, alerts){ const discovered = registrySites(registry).filter(site => !isMonitored(site)).length; const alertCount = alerts.count ?? alerts.alert_count ?? 0; const posture = alertCount > 0 || discovered > 0 ? 'Review' : 'Healthy'; set('admin-gov-posture', posture); set('admin-gov-posture-note', discovered + ' discovery item(s), ' + alertCount + ' active alert(s).'); }
  async function init(){ if(!document.querySelector('.admin-governance-depth-v1')) return; try{ const [adminTruth, footprint, registry, summary, obs, sourceState, productAccess, alerts] = await Promise.all([ json('/admin/truth').catch(()=>({})), json('/users/footprint').catch(()=>({})), json('/registry/sites').catch(()=>({})), json('/operator/summary').catch(()=>({})), json('/operator/observability').catch(()=>({})), json('/api/source-state').catch(()=>({})), json('/estate/product-access').catch(()=>({})), json('/operator/alerts').catch(()=>({})) ]); renderDiscovery(registry); renderAccess(footprint); renderProduct(adminTruth, productAccess); renderRuntime(summary, obs, sourceState); renderActions(registry, footprint, sourceState); setPosture(registry, alerts); const diag = $('admin-gov-diagnostics-json'); if(diag) diag.textContent = JSON.stringify({admin_truth_keys:Object.keys(adminTruth), footprint_summary:footprint.summary||{}, registry_summary:registry.summary||{}, source_state_keys:Object.keys(sourceState), generated_at:new Date().toISOString()}, null, 2); } catch(error){ set('admin-gov-posture','Review'); const target = $('admin-gov-action-list'); if(target) target.innerHTML = '<li>Admin governance depth failed to load: '+esc(error.message)+'</li>'; } }
  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();

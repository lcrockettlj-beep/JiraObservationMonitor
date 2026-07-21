(function(){
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = v => String(v ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  function isMonitored(site){
    const text = [site.classification,site.monitoring_status,site.monitoring_state,site.lifecycle_state,site.status,site.state,site.decision,site.policy_state].join(' ').toLowerCase();
    return site.monitored === true || site.is_monitored === true || site.in_monitoring_scope === true || text.includes('monitored') || text.includes('monitoring enabled');
  }
  function isPending(site){
    const text = [site.classification,site.monitoring_status,site.monitoring_state,site.lifecycle_state,site.status,site.state,site.decision,site.policy_state].join(' ').toLowerCase();
    return text.includes('pending');
  }
  function isRetired(site){
    const text = [site.classification,site.monitoring_status,site.monitoring_state,site.lifecycle_state,site.status,site.state,site.decision,site.policy_state].join(' ').toLowerCase();
    return text.includes('retired') || text.includes('suspended');
  }
  function key(site){return site.site_key || site.key || site.site_name || site.name || 'unknown-site';}
  function name(site){return site.site_name || site.name || site.site_key || site.key || 'Unknown site';}
  function url(site){return site.site_url || site.url || '';}
  function source(site){return Array.isArray(site.sources) ? site.sources.join(', ') : (site.source || 'registry');}
  function setText(id, value){const el=$(id); if(el) el.textContent = String(value);}
  function row(site, mode){
    const k = key(site);
    const href = mode === 'review' ? `/estate/review/${encodeURIComponent(k)}` : `/site/${encodeURIComponent(k)}`;
    const label = mode === 'review' ? 'Review Site' : 'Open Workspace';
    return `<article class="estate-life-row"><div><strong>${esc(name(site))}</strong><br><small>${esc(k)}</small></div><div>${url(site) ? `<a href="${esc(url(site))}" target="_blank" rel="noopener">${esc(url(site))}</a>` : '-'}</div><div><span class="jom-status ${mode === 'review' ? '' : 'jom-status--monitored'}">${mode === 'review' ? 'Discovered' : 'Monitored'}</span></div><div class="estate-life-actions"><a class="jom-pill jom-pill--link" href="${href}">${label}</a></div></article>`;
  }
  function renderList(id, items, mode, empty){
    const el=$(id); if(!el) return;
    el.innerHTML = items.length ? items.map(site => row(site, mode)).join('') : `<p class="estate-life-empty">${esc(empty)}</p>`;
  }
  fetch('/registry/sites', {cache:'no-store'}).then(r => {if(!r.ok) throw new Error('/registry/sites ' + r.status); return r.json();}).then(reg => {
    const sites = Array.isArray(reg.sites) ? reg.sites : [];
    const monitored = sites.filter(site => isMonitored(site) && !isRetired(site));
    const discovered = sites.filter(site => !isMonitored(site) && !isPending(site) && !isRetired(site));
    const pending = sites.filter(isPending);
    const retired = sites.filter(isRetired);
    setText('estate-life-total', sites.length);
    setText('estate-life-monitored', monitored.length);
    setText('estate-life-discovered', discovered.length);
    setText('estate-life-pending', pending.length);
    renderList('estate-life-monitored-list', monitored, 'workspace', 'No monitored sites currently recorded.');
    renderList('estate-life-discovered-list', discovered, 'review', 'No discovered sites are currently awaiting classification.');
    renderList('estate-life-pending-list', pending, 'review', 'No pending approvals currently recorded.');
    renderList('estate-life-retired-list', retired, 'review', 'No retired sites currently recorded.');
  }).catch(err => {
    console.error('Estate lifecycle failed', err);
    ['estate-life-monitored-list','estate-life-discovered-list','estate-life-pending-list','estate-life-retired-list'].forEach(id => renderList(id, [], 'review', 'Unable to load estate lifecycle data.'));
  });
})();

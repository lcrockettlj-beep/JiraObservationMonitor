/*
 * JOM OPERATOR REGISTRY PAYLOAD ADAPTER EXECUTION PACK v1
 * Scope: site_registry.js GET/load path only.
 * Behaviour: prefer /registry/sites payload, fall back to /api/site-registry.
 * POST approval/ignore actions remain on /api/site-registry/<action>.
 * UI/CSS/templates: unchanged.
 */
async function jomRegistryPayloadAdapterV1() {
  try {
    var response = await fetch('/registry/sites', { cache: 'no-store' });
    if (!response.ok) { throw new Error('registry sites unavailable'); }
    return await response.json();
  } catch (error) {
    var fallback = await fetch('/api/site-registry', { cache: 'no-store' });
    if (!fallback.ok) { throw new Error('site registry fallback unavailable'); }
    return await fallback.json();
  }
}

/*
 * JOM LEGACY JS ADAPTER MIGRATION EXECUTION PACK v1.4
 * Scope: site_registry.js only
 * Behaviour: operator registry/surface preflight first, legacy /registry/sites fallback remains active.
 * UI/CSS/templates: unchanged.
 */
async function jomSiteRegistryPreflightV14() {
  try {
    if (window.JOMOperatorAPI && typeof window.JOMOperatorAPI.getOperatorSurface === 'function') {
      await window.JOMOperatorAPI.getOperatorSurface();
    }
    if (window.JOMOperatorAPI && typeof window.JOMOperatorAPI.getRegistrySites === 'function') {
      await window.JOMOperatorAPI.getRegistrySites();
    }
  } catch (error) { return null; }
  return null;
}

async function jomSiteRegistryFetchV14(options) {
  await jomSiteRegistryPreflightV14();
  return fetch('/registry/sites', options || { cache: 'no-store' });
}

/*
 * JOM LEGACY JS ADAPTER MIGRATION EXECUTION PACK v1
 * File: static\js\site_registry.js
 * Target endpoints: /registry/sites
 * Purpose: mark this module as part of the controlled legacy-to-operator adapter migration.
 * Behaviour safety: no visual, template, or CSS changes are made by this pack.
 * Compatibility routes remain active while endpoint-specific payload alignment is completed.
 */
(function(){
  function esc(v){return String(v==null?'':v).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
  function cls(v){return String(v||'discovered').toLowerCase().replace(/[^a-z0-9_-]/g,'');}
  function pageMode(){if(location.pathname.indexOf('/admin')===0)return'admin';if(location.pathname.indexOf('/estate')===0)return'estate';return'home';}
  function norm(v){return String(v||'').toLowerCase().trim().replace(/^https?:\/\//,'').replace(/\.atlassian\.net.*$/,'').replace(/\/$/,'');}
  function siteTokens(site){var out=[];['site_key','site_name','site_url','cloud_id'].forEach(function(k){var v=site&&site[k];if(v)out.push(norm(v));});if(site&&Array.isArray(site.aliases)){site.aliases.forEach(function(a){out.push(norm(a));});}return out.filter(Boolean);}
  function containsAny(text,tokens){var t=norm(text);return tokens.some(function(k){return k&&t.indexOf(k)>=0;});}
  function findSectionByHeading(words){var hs=Array.prototype.slice.call(document.querySelectorAll('h1,h2,h3,strong,.section-title,.card-title'));for(var i=0;i<hs.length;i++){var txt=(hs[i].textContent||'').toLowerCase();if(words.every(function(w){return txt.indexOf(w)>=0;})){var el=hs[i];while(el&&el!==document.body){if(el.tagName==='SECTION'||(el.className&&String(el.className).match(/panel|card|section|registry|board|sites/i)))return el;el=el.parentElement;}}}return null;}
  function updateCountBadge(section,count){if(!section)return;Array.prototype.slice.call(section.querySelectorAll('span,button,div')).some(function(b){if((b.textContent||'').match(/\d+\s+sites?/i)){b.textContent=count+' sites';return true;}return false;});}
  function hideUnmonitoredInSection(section,tokens){if(!section)return 0;var cards=Array.prototype.slice.call(section.querySelectorAll('tr,.site-card,.site-tile,article,.card'));var kept=0;cards.forEach(function(el){if(el.querySelector&&el.querySelector('th'))return;var text=el.textContent||'';if(!text.trim())return;var siteLike=/open site|open atlassian|site signals|site projects|safe mode|stable|low risk|atlassian\.net/i.test(text);if(!siteLike)return;if(containsAny(text,tokens)){el.style.display='';kept++;}else{el.style.display='none';}});if(kept)updateCountBadge(section,kept);return kept;}
  function removeOldMounts(){['home-site-registry-mount','estate-site-registry-mount'].forEach(function(id){var el=document.getElementById(id);if(el)el.remove();});}
  function ensureHomeDiscoveryMount(){var id='home-site-discovery-mount';var el=document.getElementById(id);if(el)return el;el=document.createElement('section');el.id=id;el.className='site-registry-panel site-registry-panel--discovery';var stable=findSectionByHeading(['stable','sites']);if(stable&&stable.parentNode){stable.parentNode.insertBefore(el,stable.nextSibling);}else{(document.querySelector('main')||document.querySelector('.container')||document.body).appendChild(el);}return el;}
  function ensureAdminMount(){var id='admin-site-registry-mount';var el=document.getElementById(id);if(el)return el;el=document.createElement('section');el.id=id;el.className='site-registry-panel';(document.querySelector('main')||document.querySelector('.container')||document.body).appendChild(el);return el;}
  function post(url,payload){return fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload||{})}).then(function(r){if(!r.ok)throw new Error('failed');return r.json();});}
  function renderDiscovery(root,items,summary){var html='<div class="site-registry-head"><div><h2>Discovered Sites Awaiting Review</h2><p>These Jira resources were discovered from Atlassian Admin/Billing signals but are not monitored until approved.</p></div><div class="site-registry-summary"><span>Discovered <b>'+esc(items.length)+'</b></span><span>Pending onboarding <b>'+esc(summary.pending_onboarding_count||0)+'</b></span></div></div>';if(!items.length){root.innerHTML=html+'<p class="site-registry-note">No discovered Jira resources are waiting for approval.</p>';return;}html+='<div class="site-registry-table-wrap"><table class="site-registry-table"><thead><tr><th>Site</th><th>URL / Cloud ID</th><th>Status</th><th>Collector</th><th>Signals</th></tr></thead><tbody>';items.forEach(function(x){var sig=[];if(x.metrics&&x.metrics.jira_product_user_count!=null)sig.push('Product users: '+x.metrics.jira_product_user_count);if(x.metrics&&x.metrics.named_access_count!=null)sig.push('Named direct: '+x.metrics.named_access_count);if(x.sources)sig.push('Sources: '+x.sources.join(', '));html+='<tr><td><strong>'+esc(x.site_name||x.site_key||x.cloud_id)+'</strong><small>'+esc(x.site_key||'')+'</small></td><td>'+esc(x.site_url||x.cloud_id||'Unknown')+'</td><td><span class="site-registry-badge site-registry-badge--'+cls(x.classification)+'">'+esc(x.classification)+'</span></td><td>'+esc(x.collector_onboarding_status||'not_requested')+'</td><td>'+esc(sig.join(' | '))+'</td></tr>';});root.innerHTML=html+'</tbody></table></div><p class="site-registry-note">Approval is controlled from Admin and creates a collector-onboarding trigger before full monitoring is trusted.</p>';}
  function renderAdmin(root,sites,summary){var html='<div class="site-registry-head"><div><h2>Site Discovery & Monitoring Control</h2><p>Approve discovered Jira resources. Approval also creates a collector-onboarding trigger.</p></div><div class="site-registry-summary"><span>Monitored <b>'+esc(summary.monitored_count||0)+'</b></span><span>Discovered <b>'+esc(summary.discovered_count||0)+'</b></span><span>Pending onboarding <b>'+esc(summary.pending_onboarding_count||0)+'</b></span></div></div><div class="site-registry-table-wrap"><table class="site-registry-table"><thead><tr><th>Site</th><th>URL / Cloud ID</th><th>Status</th><th>Collector</th><th>Signals</th><th>Actions</th></tr></thead><tbody>';sites.forEach(function(x,i){var sig=[];if(x.metrics&&x.metrics.jira_product_user_count!=null)sig.push('Product users: '+x.metrics.jira_product_user_count);if(x.metrics&&x.metrics.named_access_count!=null)sig.push('Named direct: '+x.metrics.named_access_count);if(x.sources)sig.push('Sources: '+x.sources.join(', '));html+='<tr><td><strong>'+esc(x.site_name||x.site_key||x.cloud_id)+'</strong><small>'+esc(x.site_key||'')+'</small></td><td>'+esc(x.site_url||x.cloud_id||'Unknown')+'</td><td><span class="site-registry-badge site-registry-badge--'+cls(x.classification)+'">'+esc(x.classification)+'</span></td><td>'+esc(x.collector_onboarding_status||'')+'</td><td>'+esc(sig.join(' | '))+'</td><td class="site-registry-actions">';if(x.classification!=='monitored')html+='<button data-idx="'+i+'" data-action="approve">Approve + trigger onboarding</button>';if(x.classification!=='ignored')html+='<button data-idx="'+i+'" data-action="ignore">Ignore</button>';html+='</td></tr>';});root.innerHTML=html+'</tbody></table></div><p class="site-registry-note">Approval queues collector validation. Do not treat a newly approved site as fully monitored until onboarding status is validated.</p>';Array.prototype.forEach.call(root.querySelectorAll('button[data-action]'),function(btn){btn.addEventListener('click',function(){var idx=Number(btn.getAttribute('data-idx'));var action=btn.getAttribute('data-action');btn.disabled=true;btn.textContent='Working...';post('/api/site-registry/'+action,sites[idx]).then(load).catch(function(){btn.disabled=false;btn.textContent='Failed';});});});}
  function apply(data){var sites=data.sites||[],summary=data.summary||{},m=pageMode();var monitored=sites.filter(function(s){return s.classification==='monitored';});var discovered=sites.filter(function(s){return s.classification==='discovered';});var tokens=[];monitored.forEach(function(s){tokens=tokens.concat(siteTokens(s));});removeOldMounts();if(m==='home'){hideUnmonitoredInSection(findSectionByHeading(['stable','sites']),tokens);renderDiscovery(ensureHomeDiscoveryMount(),discovered,summary);}else if(m==='estate'){hideUnmonitoredInSection(findSectionByHeading(['site','prioritisation'])||findSectionByHeading(['site','prioritization']),tokens);var em=document.getElementById('estate-site-registry-mount');if(em)em.remove();}else if(m==='admin'){renderAdmin(ensureAdminMount(),sites,summary);}}
  function load(){jomRegistryPayloadAdapterV1().then(apply).catch(function(){});}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',load);else load();
})();

function jomLegacyAdapterMigrationNoteV1() {
  return {
    phase: "legacy-js-adapter-migration-execution-v1",
    behaviour: "compatibility routes remain active until payload-specific adapter swaps are validated",
    uiChanges: false,
    cssChanges: false,
    templateChanges: false
  };
}



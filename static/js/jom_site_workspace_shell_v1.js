(function(){
  'use strict';
  const siteKey=document.body.getAttribute('data-site-key')||''; const JOM_CURRENT_STATE_ALLOWED_KEYS_V1=new Set(['gli-delivery-tm','gli-global-technology','gli-it-project','gli-tracker']);
  const $=id=>document.getElementById(id);
  const setText=(id,value)=>{const el=$(id);if(el)el.textContent=value===undefined||value===null||value===''?'Unavailable':String(value)};
  const lower=value=>String(value||'').toLowerCase();
  const esc=value=>String(value??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
  const norm=value=>lower(value).replace(/^https?:\/\//,'').replace(/\.atlassian\.net.*$/,'').replace(/\/$/,'').trim();
  function unwrap(payload){return payload&&payload.data&&typeof payload.data==='object'?payload.data:(payload||{})}
  function get(obj,path,fallback){let current=obj;for(const part of String(path||'').split('.')){if(current&&typeof current==='object'&&part in current)current=current[part];else return fallback}return current===undefined||current===null?fallback:current}
  function collectSites(root){const lists=[get(root,'sites',[]),get(root,'registry.sites',[]),get(root,'site_registry.sites',[]),get(root,'inventory.sites',[])];const byKey=new Map();lists.forEach(list=>{if(Array.isArray(list)){list.forEach(item=>{if(item&&typeof item==='object'){const key=norm(keyOf(item)||urlOf(item));if(key&&!byKey.has(key))byKey.set(key,item)}})}});return Array.from(byKey.values()).filter(site=>JOM_CURRENT_STATE_ALLOWED_KEYS_V1.has(norm(keyOf(site)||urlOf(site))))}
  function keyOf(site){return String(site.site_key||site.key||site.name||site.site_name||site.url||site.site_url||'').trim()}
  function nameOf(site){return String(site.site_name||site.name||site.site_key||site.key||'Site Workspace')}
  function urlOf(site){return String(site.site_url||site.url||'').trim()}
  function lifecycleOf(site){return String(site.lifecycle||site.classification||site.status||site.collector_onboarding_status||'Review')}
  function monitoringOf(site){return site.is_monitored===true||site.monitored===true||lower(lifecycleOf(site)).includes('monitored')?'Enabled':'Review'}
  function findSite(sites){const wanted=norm(siteKey);if(!wanted)return null;return sites.find(site=>[keyOf(site),nameOf(site),urlOf(site),site.cloud_id].some(value=>norm(value)===wanted))||null}
  function setLink(id,href,show){const el=$(id);if(!el)return;el.href=href||'#';el.style.display=show?'':'none'}
  function show(id,visible){const el=$(id);if(!el)return;el.hidden=!visible;el.setAttribute('aria-hidden',visible?'false':'true')}
  function workspaceHref(site){const key=keyOf(site);return key?'/site-workspace/'+encodeURIComponent(key):'/site-workspace'}
  function renderSelector(sites){
    const list=$('workspace-selector-list');
    const count=$('workspace-selector-count');
    show('workspace-selector-panel',true);
    if(count)count.textContent=String(sites.length);
    if(!list)return;
    if(!sites.length){list.innerHTML='<p class="site-workspace-empty">No site records are available from the live Estate workspace contract.</p>';return}
    list.innerHTML=sites.map(site=>{
      const key=keyOf(site);
      const name=nameOf(site);
      const lifecycle=lifecycleOf(site);
      const monitoring=monitoringOf(site);
      return '<a class="site-workspace-selector-card" href="'+esc(workspaceHref(site))+'"><strong>'+esc(name)+'</strong><span>'+esc(key||'Site key unavailable')+'</span><small>Lifecycle: '+esc(lifecycle)+' | Monitoring: '+esc(monitoring)+'</small></a>';
    }).join('');
  }

  // JOM_SITE_WORKSPACE_MAIN_LANDING_CORRECTION_V1_1_JS START
  function updateLandingRail(sites){
    const currentSites=Array.isArray(sites)?sites:[];
    const monitored=currentSites.filter(site=>monitoringOf(site)==='Enabled');
    setText('workspace-rail-site-count',currentSites.length||'0');
    setText('workspace-rail-selected-site',siteKey?siteKey:'None');
    setText('workspace-rail-monitoring-scope',monitored.length+'/'+(currentSites.length||0));
    fetch('/api/workspace/product-users',{cache:'no-store',headers:{'Accept':'application/json'}})
      .then(response=>response.ok?response.json():null)
      .then(payload=>{
        const product=unwrap(payload||{});
        const metric=product&&product.metric?product.metric:{};
        setText('workspace-source-product-users',metric.display||metric.total||'Unavailable');
      })
      .catch(()=>setText('workspace-source-product-users','Unavailable'));
  }
  // JOM_SITE_WORKSPACE_MAIN_LANDING_CORRECTION_V1_1_JS END

  function renderNoSelection(sites){
    setText('workspace-site-title','Select Site Workspace');
    setText('workspace-site-summary','Choose a site workspace from the list below. No site-specific workspace is currently selected.');
    setText('workspace-lifecycle-pill','Select Site');
    setText('workspace-rail-key','--');
    setText('workspace-rail-lifecycle','--');
    setText('workspace-rail-monitoring','--');
    setText('workspace-source-status','Select a site workspace to load site-specific context.');
    setLink('workspace-review-link','/estate',true);
    setLink('workspace-atlassian-link','#',false);
    renderSelector(sites);
  }
  function renderSite(site){
    show('workspace-selector-panel',false);
    const key=keyOf(site);
    const url=urlOf(site);
    setText('workspace-site-title',nameOf(site));
    setText('workspace-site-summary',url||'Atlassian URL unavailable from the current Estate workspace contract.');
    setText('workspace-lifecycle-pill',lifecycleOf(site));
    setText('workspace-rail-key',key);
    setText('workspace-rail-lifecycle',lifecycleOf(site));
    setText('workspace-rail-monitoring',monitoringOf(site));
    setText('workspace-source-status','Workspace context loaded for '+nameOf(site)+'. Detailed panels will show data only when source coverage is available.');
    setLink('workspace-review-link','/estate/review/'+encodeURIComponent(key),!!key);
    setLink('workspace-atlassian-link',url,!!url);
  }
async function load(){
    try{
      const response=await fetch('/api/workspace/estate',{cache:'no-store',headers:{'Accept':'application/json'}});
      if(!response.ok)throw new Error('Estate workspace contract returned HTTP '+response.status);
      const root=unwrap(await response.json());
      const sites=collectSites(root);
      updateLandingRail(sites);
      const site=findSite(sites);
      if(!site){renderNoSelection(sites);return}
      renderSite(site);
    }catch(error){
      setText('workspace-site-title',siteKey||'Site Workspace');
      setText('workspace-source-status','Site Workspace contract unavailable: '+error.message);
      show('workspace-selector-panel',false);
    }
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',load);else load();
}());
// JOM_SITE_WORKSPACE_CONTEXT_SELECTION_V1_JS

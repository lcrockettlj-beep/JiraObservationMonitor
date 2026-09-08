(function(){
  'use strict';
  const siteKey=document.body.getAttribute('data-site-key')||'';
  const allowed=new Set(['gli-delivery-tm','gli-global-technology','gli-it-project','gli-tracker']);
  const $=id=>document.getElementById(id);
  const text=(id,value)=>{const el=$(id);if(el)el.textContent=value===undefined||value===null||value===''?'Unavailable':String(value)};
  const norm=value=>String(value||'').toLowerCase().replace(/^https?:\/\//,'').replace(/\.atlassian\.net.*$/,'').replace(/\/$/,'').trim();
  const esc=value=>String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const unwrap=payload=>payload&&payload.data&&typeof payload.data==='object'?payload.data:(payload||{});
  const get=(obj,path,fallback)=>{let current=obj;for(const part of String(path||'').split('.')){if(current&&typeof current==='object'&&part in current)current=current[part];else return fallback}return current===undefined||current===null?fallback:current};
  const keyOf=site=>String(site.site_key||site.key||site.name||site.site_name||site.url||site.site_url||'').trim();
  const nameOf=site=>String(site.site_name||site.name||site.site_key||site.key||'Site Workspace');
  const urlOf=site=>String(site.site_url||site.url||'').trim();
  const lifecycleOf=site=>String(site.lifecycle||site.classification||site.status||site.collector_onboarding_status||'Review');
  const monitoringOf=site=>site.is_monitored===true||site.monitored===true||lifecycleOf(site).toLowerCase().includes('monitored')?'Enabled':'Review';
  const show=(id,visible)=>{const el=$(id);if(el){el.hidden=!visible;el.setAttribute('aria-hidden',visible?'false':'true')}};
  const projectKey=row=>`${norm(row.site_key)}::${String(row.project_key||'').toUpperCase()}`;
  const names=rows=>Array.isArray(rows)?rows.map(item=>item&&item.display_name).filter(Boolean).join(', ')||'Unavailable':'Unavailable';
  async function json(url){const response=await fetch(url,{cache:'no-store',headers:{Accept:'application/json'}});let payload={};try{payload=await response.json()}catch(_error){}if(!response.ok)throw new Error(payload.reason||`${url} returned HTTP ${response.status}`);return payload}
  function collectSites(root){const lists=[get(root,'sites',[]),get(root,'registry.sites',[]),get(root,'site_registry.sites',[]),get(root,'inventory.sites',[])],map=new Map();lists.forEach(list=>Array.isArray(list)&&list.forEach(item=>{if(item&&typeof item==='object'){const key=norm(keyOf(item)||urlOf(item));if(key&&!map.has(key))map.set(key,item)}}));return Array.from(map.values()).filter(site=>allowed.has(norm(keyOf(site)||urlOf(site))));}
  function selector(sites){show('workspace-selector-panel',true);text('workspace-selector-count',sites.length);const host=$('workspace-selector-list');if(!host)return;host.innerHTML=sites.length?sites.map(site=>`<a class="site-workspace-selector-card" href="/site-workspace/${encodeURIComponent(keyOf(site))}"><strong>${esc(nameOf(site))}</strong><span>${esc(keyOf(site)||'Site key unavailable')}</span><small>Lifecycle: ${esc(lifecycleOf(site))} | Monitoring: ${esc(monitoringOf(site))}</small></a>`).join(''):'<p class="site-workspace-empty">No site records are available from the Estate workspace contract.</p>';}
  function siteMatch(sites){const wanted=norm(siteKey);return wanted?sites.find(site=>[keyOf(site),nameOf(site),urlOf(site),site.cloud_id].some(value=>norm(value)===wanted))||null:null}
  function rail(sites){const monitored=sites.filter(site=>monitoringOf(site)==='Enabled');text('workspace-rail-site-count',sites.length);text('workspace-rail-selected-site',siteKey||'None');text('workspace-rail-monitoring-scope',`${monitored.length}/${sites.length}`);json('/api/workspace/product-users').then(payload=>{const metric=unwrap(payload).metric||{};text('workspace-source-product-users',metric.display||metric.total||'Unavailable')}).catch(()=>text('workspace-source-product-users','Unavailable'));}
  function recordMap(rows){return new Map((Array.isArray(rows)?rows:[]).map(row=>[projectKey(row),row]));}
  async function projects(selected){
    show('workspace-project-panel',true);text('workspace-source-projects','Checking');
    try{
      const [inventory,leads,owners]=await Promise.all([json('/api/governance/projects'),json('/api/governance/projects/leads'),json('/api/governance/projects/owners')]);
      const all=Array.isArray(inventory.projects)?inventory.projects:[],leadRows=Array.isArray(leads.projects)?leads.projects:[],ownerRows=Array.isArray(owners.projects)?owners.projects:[];
      const inventoryKeys=new Set(all.map(projectKey)),leadKeys=new Set(leadRows.map(projectKey)),ownerKeys=new Set(ownerRows.map(projectKey));
      if(inventoryKeys.size!==leadKeys.size||inventoryKeys.size!==ownerKeys.size||[...inventoryKeys].some(key=>!leadKeys.has(key)||!ownerKeys.has(key)))throw new Error('Project authorities are not synchronized. Refresh the live authority chain.');
      const wanted=norm(keyOf(selected)||siteKey),lm=recordMap(leadRows),om=recordMap(ownerRows);
      const rows=all.filter(row=>norm(row.site_key)===wanted).map(row=>{const lead=lm.get(projectKey(row))||{},owner=om.get(projectKey(row))||{},leadNames=names(lead.leads),ownerNames=names(owner.owners),hasLead=Array.isArray(lead.leads)&&lead.leads.length>0,owned=Array.isArray(owner.owners)&&owner.owners.length>0;return {...row,leadNames,ownerNames,owned,state:owned?'Owned':hasLead?'Owner unavailable':'Lead and owner unavailable'}});
      const owned=rows.filter(row=>row.owned).length,gaps=rows.length-owned,coverage=rows.length?Math.round((owned/rows.length)*1000)/10:null;
      text('workspace-project-count',`${rows.length} projects`);text('workspace-summary-projects',rows.length);text('workspace-summary-owned',owned);text('workspace-summary-coverage',coverage===null?'Unavailable':`${coverage}%`);text('workspace-summary-gaps',gaps);text('workspace-source-projects',rows.length);text('workspace-project-status',`Current synchronized authority for ${nameOf(selected)}. Missing evidence remains unavailable.`);
      const body=$('workspace-project-rows');body.innerHTML=rows.map(row=>`<tr><td>${esc(row.project_name)}</td><td>${esc(row.project_key)}</td><td>${esc(row.project_type_key)}</td><td>${esc(row.leadNames)}</td><td>${esc(row.ownerNames)}</td><td><span class="site-workspace-state ${row.owned?'site-workspace-state--ok':'site-workspace-state--gap'}">${esc(row.state)}</span></td></tr>`).join('');
      show('workspace-project-empty',rows.length===0);if(!rows.length)body.innerHTML='';
    }catch(error){text('workspace-source-projects','Unavailable');text('workspace-project-count','Unavailable');text('workspace-project-status',error.message);const body=$('workspace-project-rows');if(body)body.innerHTML=`<tr><td colspan="6">${esc(error.message)}</td></tr>`;}
  }
  async function load(){try{const root=unwrap(await json('/api/workspace/estate')),sites=collectSites(root);rail(sites);const selected=siteMatch(sites);if(!selected){text('workspace-site-title','Select Site Workspace');text('workspace-site-summary','Choose a site workspace from the list below. No site-specific workspace is selected.');text('workspace-source-status','Select a site workspace to load site-specific authority.');selector(sites);return}show('workspace-selector-panel',false);text('workspace-site-title',nameOf(selected));text('workspace-site-summary',urlOf(selected)||'Atlassian URL unavailable from the current Estate workspace contract.');text('workspace-rail-context',nameOf(selected));text('workspace-source-status','Current Estate, Product Access and Project Governance contracts are loaded read-only.');await projects(selected)}catch(error){text('workspace-site-title',siteKey||'Site Workspace');text('workspace-source-status',`Site Workspace contract unavailable: ${error.message}`);show('workspace-selector-panel',false)}}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',load);else load();
}());

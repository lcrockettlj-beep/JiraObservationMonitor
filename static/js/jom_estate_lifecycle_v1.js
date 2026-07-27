// JOM Estate Lifecycle v1 - single owner, no sidecar
(function(){
  'use strict';
  let contract={},data={},sites=[];
  const $=id=>document.getElementById(id);
  const set=(id,v)=>{const e=$(id);if(e)e.textContent=(v==null||v==='')?'n/a':String(v);};
  const num=(v,f)=>{const n=Number(v);return Number.isFinite(n)?n:f;};
  const esc=v=>String(v??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#039;');
  const unwrap=p=>(p&&typeof p==='object'&&p.data&&typeof p.data==='object')?p.data:(p&&typeof p==='object'?p:{});
  function payload(c){const d=unwrap(c||contract),p=unwrap(d.payload||{}),r=unwrap(d.registry||d.site_registry||{});if(Array.isArray(d.sites))return d;if(Array.isArray(p.sites))return p;if(Array.isArray(r.sites))return r;return r;}
  function getSites(c){const p=payload(c);return Array.isArray(p.sites)?p.sites.filter(x=>x&&typeof x==='object'):[];}
  function summary(c){const d=unwrap(c||contract),p=unwrap(d.payload||{}),r=payload(c);return d.summary||p.summary||d.registry_summary||r.summary||{};}
  function key(s){return s.site_key||s.key||s.cloud_id||s.site_name||s.name||'site';}
  function label(s){return s.site_name||s.name||s.site_key||s.key||s.site_url||s.url||'Unknown site';}
  function url(s){return s.site_url||s.url||'';}
  function life(s){return String(s&&(s.lifecycle||s.classification||s.collector_onboarding_status||s.status)||'review');}
  function monitored(s){const l=life(s).toLowerCase();return !!(s&&(s.is_monitored===true||s.monitored===true||l==='monitored'||l.includes('monitoring enabled')));}
  function pending(s){const l=life(s).toLowerCase();return l.includes('pending')||String(s.collector_onboarding_status||'').toLowerCase().includes('pending')||s.can_approve===true;}
  function health(s){const v=String(s.health||s.health_status||s.source_status||s.status||'not available').toLowerCase();if(v==='ok'||v==='monitored')return'OK';if(v==='error'||v==='failed'||v==='review')return'Review';return v==='not available'?'Not available':v;}
  function last(s){const r=payload(contract);return s.last_observed_at||s.last_observation_at||s.last_seen_at||s.updated_at_utc||s.generated_at_utc||s.generated_at||r.generated_at_utc||data.generated_at_utc||contract.generated_at_utc||contract.served_at_utc||'Source timestamp unavailable';}
  function searchMatch(s,q){q=String(q||'').trim().toLowerCase();if(!q)return true;return [s.site_name,s.name,s.site_key,s.key,s.cloud_id,s.url,s.site_url,s.lifecycle,s.classification,s.status,s.collector_onboarding_status].filter(Boolean).join(' ').toLowerCase().includes(q);}
  function visible(){const q=$('estate-search')?$('estate-search').value:'';return sites.filter(monitored).filter(s=>searchMatch(s,q));}
  function siteCell(s){const u=url(s),t=esc(label(s));return u?'<a class="estate-site-link" href="'+esc(u)+'" target="_blank" rel="noopener noreferrer">'+t+'</a>':t;}
  function actionCell(s){return'<a class="estate-site-link estate-site-link--button" href="/estate/review/'+encodeURIComponent(key(s))+'">Manage</a>';}
  async function fetchContract(){const r=await fetch('/api/estate/admin-site-inventory',{cache:'no-store'});if(!r.ok)throw new Error('/api/estate/admin-site-inventory returned '+r.status);return r.json();}
  function renderRail(c){const s=summary(c),rows=getSites(c),p=payload(c);const total=num(s.total_sites??s.total_inventory_rows??s.live_resource_count,rows.length),mon=num(s.monitored_count,rows.filter(monitored).length),disc=num(s.discovered_count,rows.filter(x=>life(x).toLowerCase()==='discovered').length),pend=num(s.pending_onboarding_count??s.pending_review_count,rows.filter(pending).length),ign=num(s.ignored_count,rows.filter(x=>life(x).toLowerCase()==='ignored').length);set('rail-total-sites',total);set('rail-monitored-sites',mon);set('rail-discovered-sites',disc);set('rail-review-queue',disc+pend);set('rail-pending-sites',pend);set('rail-ignored-sites',ign);set('rail-registry-status',data.registry_status||p.status||'OK');set('rail-users-count','--');set('rail-alert-count',0);}
  function renderRows(rows){const b=$('estate-registry-body');if(!b)return;if(!rows.length){b.innerHTML='<tr><td colspan="6">No monitored sites match the current search.</td></tr>';return;}b.innerHTML=rows.map(s=>'<tr><td>'+siteCell(s)+'</td><td>'+esc(life(s))+'</td><td>'+esc(monitored(s)?'Monitored':'Not monitored')+'</td><td>'+esc(health(s))+'</td><td>'+esc(last(s))+'</td><td>'+actionCell(s)+'</td></tr>').join('');}
  function renderQueue(c){const list=$('estate-review-list'),count=$('estate-review-count'),rows=getSites(c).filter(s=>life(s).toLowerCase()==='discovered'||pending(s));if(count)count.textContent=String(rows.length);if(!list)return;if(!rows.length){list.innerHTML='<p class="estate-empty">No sites currently awaiting Estate review.</p>';return;}list.innerHTML=rows.map(s=>'<div class="estate-review-item"><strong>'+esc(label(s))+'</strong><a class="estate-site-link estate-site-link--button" href="/estate/review/'+encodeURIComponent(key(s))+'">Review</a></div>').join('');}
  function error(e){const m=e&&e.message?e.message:String(e||'Unknown error'),b=$('estate-registry-body'),l=$('estate-review-list');if(b)b.innerHTML='<tr><td colspan="6">Estate render error: '+esc(m)+'</td></tr>';if(l)l.innerHTML='<p class="estate-empty">Estate render error: '+esc(m)+'</p>';set('rail-registry-status','review');}
  async function load(){try{contract=await fetchContract();data=unwrap(contract);sites=getSites(contract);renderRail(contract);renderRows(visible());renderQueue(contract);}catch(e){console.warn('Estate workspace contract load failed',e);error(e);}}
  function init(){const s=$('estate-search'),f=$('estate-filter');if(s)s.addEventListener('input',()=>renderRows(visible()));if(f)f.addEventListener('change',()=>renderRows(visible()));load();}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();

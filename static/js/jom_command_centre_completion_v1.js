(function(){
  'use strict';
  const ENDPOINT='/api/workspace/command-centre';const JOM_CURRENT_STATE_ALLOWED_KEYS_V1=new Set(['gli-delivery-tm','gli-global-technology','gli-it-project','gli-tracker']); function currentKey(s){return String((s&& (s.site_key||s.key||s.site_name||s.name||s.url||s.site_url))||'').toLowerCase().replace(/^https?:\/\//,'').replace(/\.atlassian\.net.*$/,'').trim();} function currentSite(s){const k=currentKey(s);return JOM_CURRENT_STATE_ALLOWED_KEYS_V1.has(k);} 
  const asArray=v=>Array.isArray(v)?v:[];
  const asNumber=(v,f)=>{const n=Number(v);return Number.isFinite(n)?n:f;};
  const unwrap=p=>(p&&typeof p==='object'&&p.data&&typeof p.data==='object')?p.data:(p&&typeof p==='object'?p:{});
  function get(o,path,f){let c=o;for(const p of String(path||'').split('.')){if(c&&typeof c==='object'&&p in c)c=c[p];else return f;}return c==null?f:c;}
  function setText(id,v,state){const e=document.getElementById(id);if(!e)return;e.textContent=(v==null||v==='')?'n/a':String(v);if(state)e.setAttribute('data-state',state);}
  function setNote(id,v){const e=document.getElementById(id);if(e)e.textContent=v;}
  function setHtml(id,v){const e=document.getElementById(id);if(e)e.innerHTML=v;}
  function esc(v){return String(v??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#039;');}
  async function load(){const r=await fetch(ENDPOINT,{cache:'no-store'});if(!r.ok)throw new Error(ENDPOINT+' returned '+r.status);return unwrap(await r.json());}
  function state(s){return String(s&&(s.lifecycle||s.classification||s.status||s.state||s.monitoring_state||s.collector_onboarding_status)||'').toLowerCase();}
  function monitored(s){const t=state(s);return !!(s&&(s.is_monitored===true||s.monitored===true||s.in_monitoring_scope===true||t==='monitored'||t.includes('monitoring enabled')));}
  function ignored(s){const t=state(s);return t.includes('ignored')||t.includes('retired');}
  function discovered(s){const t=state(s);return !!(s&&!monitored(s)&&!ignored(s)&&(t==='discovered'||t.includes('review')||t.includes('pending')||t.includes('gap')));}
  function registry(root){
    const reg=unwrap(get(root,'registry',get(root,'site_registry',{})));
    const sites=asArray(reg.sites||get(root,'sites',[])).filter(currentSite);
    const sum=get(root,'registry_summary',get(reg,'summary',get(root,'summary',{})))||{};
    const total=asNumber(sum.total_sites??sum.site_count,sites.length);
    const mon=asNumber(sum.monitored_count,sites.filter(monitored).length);
    const disc=asNumber(sum.discovered_count,sites.filter(discovered).length);
    const pending=asNumber(sum.pending_onboarding_count??sum.pending_count,sites.filter(s=>state(s).includes('pending')).length);
    const review=asNumber(sum.review_count,Math.max(disc,pending,0));
    const coverage=total>0?Math.round((mon/total)*100):0;
    return{total,monitored:mon,discovered:disc,pending,review,coverage,sites};
  }
  function organisations(root){return asNumber(get(root,'organisations.metric',null),null);}
  function users(root){for(const v of [get(root,'users.metric',null),get(root,'users_metric.metric',null),get(root,'users_metric',null),get(root,'users.summary.total_product_access_assignments',null),get(root,'users.summary.total_jira_product_user_count',null),get(root,'estate_product_access.summary.total_jira_product_user_count',null)]){const n=asNumber(v,null);if(n!==null)return n;}return null;}
  function dataConfidence(root,r,u,o){const ok=!!(r&&r.total>0&&r.monitored!==null&&r.review!==null&&u!==null&&o!==null);const liveOrg=get(root,'organisations.live_collection',null);if(liveOrg===false)return{label:'Review',state:'review'};return ok?{label:'High',state:'high'}:{label:'Review',state:'review'};}
  function runtime(root){const v=String(get(root,'operator_summary.runtime.last_result_status',get(root,'operator_summary.runtime.state',get(root,'runtime.state','ok')))||'').toLowerCase();if(v.includes('fail')||v.includes('error')||v.includes('critical'))return'Review';if(v.includes('running'))return'Running';return'OK';}
  function key(a){const title=String(a.title||a.message||'').toLowerCase();const src=String(a.source||a.category||'').toLowerCase();if(title.includes('discovered')||src.includes('site_registry'))return'discovered-sites';if(title.includes('admin truth')||src.includes('admin_truth'))return'admin-truth';return title+'|'+src;}
  function sev(a){const r=String(a.level||a.severity||a.priority||'').toLowerCase();if(r.includes('critical')||r.includes('error')||r.includes('fail'))return'critical';if(r.includes('high')||r.includes('warning')||r.includes('warn'))return'high';if(r.includes('review')||r.includes('medium'))return'review';if(r.includes('ok')||r.includes('healthy'))return'ok';return'info';}
  function rank(l){return{critical:0,high:1,review:2,info:3,ok:4}[l]??3;}
  function href(a){const k=key(a);const s=String(a.source||a.category||'').toLowerCase();if(k==='discovered-sites'||s.includes('estate_lifecycle')||s.includes('estate_admin_site_inventory'))return'/estate#discovered-sites';return(s.includes('runtime')||s.includes('operator'))?'/operator/observability':'/estate';}
  function label(a){const k=key(a);const s=String(a.source||a.category||'').toLowerCase();if(k==='discovered-sites'||s.includes('estate_lifecycle')||s.includes('estate_admin_site_inventory'))return'Open Estate review';return(s.includes('runtime')||s.includes('operator'))?'Open Runtime Status':'Open workspace';}
  function actions(root){const primary=asArray(get(root,'operator_alerts.alerts',[]));const fallback=primary.length?[]:[...asArray(get(root,'operator_summary.top_alerts',[])),...asArray(get(root,'alerts',[]))];const out=[...primary,...fallback];const seen=new Set();return out.filter(x=>{if(!x||typeof x!=='object')return false;const k=key(x);if(seen.has(k))return false;seen.add(k);return true;}).sort((a,b)=>rank(sev(a))-rank(sev(b))).slice(0,6);}



  // JOM_COMMAND_CENTRE_LIVE_NOC_DISPLAY_V1 START
  function nocSiteName(site){return String((site&&(site.site_name||site.name||site.site_key||site.key))||'Site');}
  function nocSiteKey(site){return String((site&&(site.site_key||site.key||site.site_name||site.name))||'site').toLowerCase().replace(/[^a-z0-9_-]+/g,'-');}
  function renderNocDisplay(root,r){
    const canvas=document.getElementById('jom-noc-canvas');
    if(!canvas)return;
    const sites=asArray(r.sites).filter(site=>currentSite(site)&&monitored(site)&&!ignored(site));
    setText('jom-noc-node-count',sites.length);
    setText('jom-noc-coverage',r.coverage+'%');
    if(!sites.length){canvas.innerHTML='<div class="jom-noc-empty"><strong>No monitored site nodes are currently active.</strong><span>Enable monitoring from Site Review to populate the live topology.</span></div>';return;}
    const cx=500,cy=190,rx=285,ry=98;
    const nodes=sites.map((site,index)=>{const angle=(-90+(360/sites.length)*index)*Math.PI/180;return{site,index,x:Math.round(cx+Math.cos(angle)*rx),y:Math.round(cy+Math.sin(angle)*ry),name:nocSiteName(site),key:nocSiteKey(site)};});
    const defs=nodes.map(n=>'<path id="noc-link-'+n.index+'" d="M '+cx+' '+cy+' L '+n.x+' '+n.y+'" />').join('');
    const links=nodes.map(n=>'<use href="#noc-link-'+n.index+'" class="jom-noc-link"/><circle class="jom-noc-packet" r="4"><animateMotion dur="'+(4+n.index%3)+'s" repeatCount="indefinite" begin="'+(n.index*.35)+'s"><mpath href="#noc-link-'+n.index+'"/></animateMotion></circle>').join('');
    const siteNodes=nodes.map(n=>'<g class="jom-noc-site" transform="translate('+n.x+' '+n.y+')"><circle class="jom-noc-node-ring" r="30"/><circle class="jom-noc-node" r="16"/><text class="jom-noc-label" y="42">'+esc(n.name)+'</text></g>').join('');
    canvas.innerHTML='<svg class="jom-noc-svg" viewBox="0 0 1000 420" role="img" aria-label="Live organisation to monitored sites topology"><defs>'+defs+'<radialGradient id="noc-org-glow" cx="50%" cy="50%" r="50%"><stop offset="0%" stop-color="#0f62fe" stop-opacity=".95"/><stop offset="100%" stop-color="#0f62fe" stop-opacity=".12"/></radialGradient></defs><rect class="jom-noc-grid" x="0" y="0" width="1000" height="420" rx="24"/>'+links+'<g class="jom-noc-org" transform="translate('+cx+' '+cy+')"><circle class="jom-noc-org-pulse" r="64"/><circle class="jom-noc-org-core" r="38"/><text class="jom-noc-org-label" y="72">GLI</text></g>'+siteNodes+'<circle class="jom-noc-sweep" cx="'+cx+'" cy="'+cy+'" r="176"/></svg>';
  }
  // JOM_COMMAND_CENTRE_LIVE_NOC_DISPLAY_V1 END

  function setActionQueueVisible(visible){const list=document.getElementById('jom-final-risk-list');if(!list)return;const card=list.closest('section,article,.jom-final-card,.jom-rail-card,.jom-card');if(card){card.hidden=false;card.setAttribute('aria-hidden','false');}list.hidden=false;list.setAttribute('aria-hidden','false');}
  function note(r,a){if(!a.length)return'No immediate estate actions found.';const n=a.length;return n===1?'1 operational item requires review.':n+' operational items require review.';}
  function render(root){const r=registry(root),u=users(root),o=organisations(root),a=actions(root),rt=runtime(root);const ring=document.querySelector('.jom-coverage-ring');if(ring)ring.style.setProperty('--coverage-deg',Math.max(0,Math.min(360,r.coverage*3.6))+'deg');const mb=document.getElementById('jom-rail-coverage-monitored'),rb=document.getElementById('jom-rail-coverage-review');if(mb)mb.style.width=Math.max(0,Math.min(100,r.coverage))+'%';if(rb)rb.style.width=Math.max(0,Math.min(100,100-r.coverage))+'%';setText('jom-rail-monitoring-coverage',r.coverage+'%');setText('jom-rail-coverage-reason',r.monitored+'/'+r.total+' sites monitored');setText('jom-rail-total-sites',r.total);setText('jom-rail-monitored-sites',r.monitored);setText('jom-rail-review-items',r.review);setText('jom-rail-organisations',o===null?'n/a':o);const health=(rt==='Review')?{l:'Critical',s:'critical'}:(r.review||a.length)?{l:'Needs Attention',s:'attention'}:{l:'Healthy',s:'healthy'};setText('jom-rail-overall-health',health.l,health.s);setNote('jom-hero-health-note',note(r,a));const dc=dataConfidence(root,r,u,o);setText('jom-rail-data-health',dc.label,dc.state);setText('jom-rail-runtime',rt,rt==='OK'?'ok':'review');setText('jom-rail-alerts',a.length);setText('jom-rail-users',u===null?'n/a':u);renderNocDisplay(root,r);if(!a.length){setActionQueueVisible(true);setHtml('jom-final-risk-list','<article class="jom-final-risk-card"><span class="jom-risk-pill jom-risk-pill--ok">ok</span><h3>No immediate operational actions</h3><p><strong>Current position:</strong> Command Centre has no active alert items to action.</p><p><strong>Next step:</strong> Continue monitoring estate health and source freshness.</p></article>');return;}setActionQueueVisible(true);setHtml('jom-final-risk-list',a.map(x=>{const item={level:sev(x),title:String(x.title||x.message||'Action required'),impact:String(x.impact||x.reason||x.description||'This item needs review.'),action:String(x.action||x.recommended_action||'Review the related workspace.'),source:String(x.source||x.category||'JOM'),href:href(x),button:String(x.action_label||label(x))};return'<article class="jom-final-risk-card"><span class="jom-risk-pill jom-risk-pill--'+esc(item.level)+'">'+esc(item.level)+'</span><h3>'+esc(item.title)+'</h3><p><strong>Why this matters:</strong> '+esc(item.impact)+'</p><p><strong>Next step:</strong> '+esc(item.action)+'</p><div class="jom-final-action-row"><a class="jom-final-action" href="'+esc(item.href)+'">'+esc(item.button)+'</a></div></article>';}).join(''));}
  function unavailable(m){['jom-rail-monitoring-coverage','jom-rail-organisations','jom-rail-total-sites','jom-rail-monitored-sites','jom-rail-review-items','jom-rail-alerts','jom-rail-users','jom-rail-runtime','jom-rail-data-health'].forEach(id=>setText(id,'n/a'));setText('jom-rail-overall-health','Review','review');setNote('jom-hero-health-note','Command Centre data is temporarily unavailable.');setText('jom-rail-data-health','Review','review');setText('jom-rail-runtime','Review','review');setHtml('jom-final-risk-list','<div class="jom-final-empty">Command Centre data is temporarily unavailable. '+esc(m||'')+'</div>');}
  function boot(){load().then(render).catch(e=>{console.warn('Command Centre workspace renderer failed',e);unavailable(e&&e.message);});}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();

/* JOM_COMMAND_CENTRE_ACTION_DEDUPLICATION_V1: frontend generic Estate review fallback removed; backend lifecycle alert is source of truth. */

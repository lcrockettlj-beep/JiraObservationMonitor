(function(){
  'use strict';
  const ENDPOINT='/api/workspace/command-centre';
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
    const sites=asArray(reg.sites||get(root,'sites',[]));
    const sum=get(root,'registry_summary',get(reg,'summary',get(root,'summary',{})))||{};
    const total=asNumber(sum.total_sites??sum.site_count,sites.length);
    const mon=asNumber(sum.monitored_count,sites.filter(monitored).length);
    const disc=asNumber(sum.discovered_count,sites.filter(discovered).length);
    const pending=asNumber(sum.pending_onboarding_count??sum.pending_count,sites.filter(s=>state(s).includes('pending')).length);
    const review=asNumber(sum.review_count,Math.max(disc,pending,0));
    const coverage=total>0?Math.round((mon/total)*100):0;
    return{total,monitored:mon,discovered:disc,pending,review,coverage,sites};
  }
  function users(root){for(const v of [get(root,'users.metric',null),get(root,'users_metric.metric',null),get(root,'users_metric',null),get(root,'users.summary.total_product_access_assignments',null),get(root,'users.summary.total_jira_product_user_count',null),get(root,'estate_product_access.summary.total_jira_product_user_count',null)]){const n=asNumber(v,null);if(n!==null)return n;}return null;}
  function runtime(root){const v=String(get(root,'operator_summary.runtime.last_result_status',get(root,'operator_summary.runtime.state',get(root,'runtime.state','ok')))||'').toLowerCase();if(v.includes('fail')||v.includes('error')||v.includes('critical'))return'Review';if(v.includes('running'))return'Running';return'OK';}
  function key(a){const title=String(a.title||a.message||'').toLowerCase();const src=String(a.source||a.category||'').toLowerCase();if(title.includes('discovered')||src.includes('site_registry'))return'discovered-sites';if(title.includes('admin truth')||src.includes('admin_truth'))return'admin-truth';return title+'|'+src;}
  function sev(a){const r=String(a.level||a.severity||a.priority||'').toLowerCase();if(r.includes('critical')||r.includes('error')||r.includes('fail'))return'critical';if(r.includes('high')||r.includes('warning')||r.includes('warn'))return'high';if(r.includes('review')||r.includes('medium'))return'review';if(r.includes('ok')||r.includes('healthy'))return'ok';return'info';}
  function rank(l){return{critical:0,high:1,review:2,info:3,ok:4}[l]??3;}
  function href(a){const k=key(a);if(k==='discovered-sites')return'/estate#site-registry';if(k==='admin-truth')return'/reference';const s=String(a.source||a.category||'').toLowerCase();return(s.includes('runtime')||s.includes('operator'))?'/operator/observability':'/estate';}
  function label(a){const k=key(a);if(k==='discovered-sites')return'Open Estate review';if(k==='admin-truth')return'Open Admin';const s=String(a.source||a.category||'').toLowerCase();return(s.includes('runtime')||s.includes('operator'))?'Open Runtime Status':'Open workspace';}
  function actions(root){const out=[...asArray(get(root,'operator_alerts.alerts',[])),...asArray(get(root,'operator_summary.top_alerts',[])),...asArray(get(root,'alerts',[]))];const seen=new Set();return out.filter(x=>{if(!x||typeof x!=='object')return false;const k=key(x);if(seen.has(k))return false;seen.add(k);return true;}).sort((a,b)=>rank(sev(a))-rank(sev(b))).slice(0,6);}
  function note(r,a){if(!a.length)return'No immediate estate actions found.';if(key(a[0])==='discovered-sites')return'Estate review: one or more sites need lifecycle classification.';return String(a[0].title||a[0].message||'Top action requires review.');}
  function render(root){const r=registry(root),u=users(root),a=actions(root),rt=runtime(root);const ring=document.querySelector('.jom-coverage-ring');if(ring)ring.style.setProperty('--coverage-deg',Math.max(0,Math.min(360,r.coverage*3.6))+'deg');const mb=document.getElementById('jom-rail-coverage-monitored'),rb=document.getElementById('jom-rail-coverage-review');if(mb)mb.style.width=Math.max(0,Math.min(100,r.coverage))+'%';if(rb)rb.style.width=Math.max(0,Math.min(100,100-r.coverage))+'%';setText('jom-rail-monitoring-coverage',r.coverage+'%');setText('jom-rail-coverage-reason',r.monitored+'/'+r.total+' sites monitored');setText('jom-rail-total-sites',r.total);setText('jom-rail-monitored-sites',r.monitored);setText('jom-rail-review-items',r.review);const health=(rt==='Review')?{l:'Critical',s:'critical'}:(r.review||a.length)?{l:'Needs Attention',s:'attention'}:{l:'Healthy',s:'healthy'};setText('jom-rail-overall-health',health.l,health.s);setNote('jom-hero-health-note',note(r,a));setText('jom-rail-data-health',r.total>0?'High':'Review',r.total>0?'high':'review');setText('jom-rail-runtime',rt,rt==='OK'?'ok':'review');setText('jom-rail-alerts',a.length);setText('jom-rail-users',u===null?'n/a':u);if(!a.length){setHtml('jom-final-risk-list','<div class="jom-final-empty">No immediate actions found.</div>');return;}setHtml('jom-final-risk-list',a.map(x=>{const item={level:sev(x),title:String(x.title||x.message||'Action required'),impact:String(x.impact||x.reason||x.description||'This item needs review.'),action:String(x.action||x.recommended_action||'Review the related workspace.'),source:String(x.source||x.category||'JOM'),href:href(x),button:label(x)};return'<article class="jom-final-risk-card"><span class="jom-risk-pill jom-risk-pill--'+esc(item.level)+'">'+esc(item.level)+'</span><h3>'+esc(item.title)+'</h3><p><strong>Impact:</strong> '+esc(item.impact)+'</p><p><strong>Recommended action:</strong> '+esc(item.action)+'</p><p><strong>Source:</strong> '+esc(item.source)+'</p><div class="jom-final-action-row"><a class="jom-final-action" href="'+esc(item.href)+'">'+esc(item.button)+'</a></div></article>';}).join(''));}
  function unavailable(m){['jom-rail-monitoring-coverage','jom-rail-total-sites','jom-rail-monitored-sites','jom-rail-review-items','jom-rail-alerts','jom-rail-users'].forEach(id=>setText(id,'n/a'));setText('jom-rail-overall-health','Review','review');setNote('jom-hero-health-note','Command Centre data is temporarily unavailable.');setText('jom-rail-data-health','Review','review');setText('jom-rail-runtime','Review','review');setHtml('jom-final-risk-list','<div class="jom-final-empty">Command Centre data is temporarily unavailable. '+esc(m||'')+'</div>');}
  function boot(){load().then(render).catch(e=>{console.warn('Command Centre workspace renderer failed',e);unavailable(e&&e.message);});}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();

/* JOM_COMMAND_CENTRE_ACTION_DEDUPLICATION_V1: frontend generic Estate review fallback removed; backend lifecycle alert is source of truth. */

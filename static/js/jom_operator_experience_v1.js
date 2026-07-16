/* JOM UI Alignment & Operator Experience v1 */
(function(){
  const endpoints = {summary:'/operator/summary',alerts:'/operator/alerts',registry:'/registry/sites'};
  async function getJson(url){ const r = await fetch(url,{cache:'no-store'}); if(!r.ok) throw new Error(url+' '+r.status); return r.json(); }
  function safe(v,f){ return (v===null||v===undefined||v==='') ? (f||'Unavailable') : String(v); }
  function runtimeLabel(summary){ const rt=(summary&&summary.runtime)||{}; const s=rt.last_result_status||rt.state||'unknown'; return String(s).toLowerCase()==='ok'?'OK':safe(s,'Unknown'); }
  function sourceLabel(summary){ const sh=(summary&&summary.source_health)||{}; if(sh.issue_count!==undefined) return Number(sh.issue_count)===0?'OK':'Review'; return safe(sh.status,'Review'); }
  function registryLabel(reg){ const s=(reg&&reg.summary)||{}; const total=s.total_sites??s.discovered_count??(Array.isArray(reg&&reg.sites)?reg.sites.length:0); return total+' sites'; }
  function discoveryLabel(reg){ const s=(reg&&reg.summary)||{}; const c=s.discovered_count??s.pending_onboarding_count??0; return c+' discovered'; }
  function alertLabel(alerts){ const c=alerts&&alerts.count!==undefined?alerts.count:(Array.isArray(alerts&&alerts.alerts)?alerts.alerts.length:0); return c+' active'; }
  function item(label,value){ const d=document.createElement('div'); d.className='jom-operator-status-pill'; const s=document.createElement('span'); s.textContent=label; const b=document.createElement('strong'); b.textContent=value; d.appendChild(s); d.appendChild(b); return d; }
  function insertBar(values){ if(document.querySelector('.jom-operator-status-bar')) return; const bar=document.createElement('section'); bar.className='jom-operator-status-bar'; bar.setAttribute('aria-label','Live operator status'); [['Runtime',values.runtime],['Sources',values.sources],['Registry',values.registry],['Discovery',values.discovery],['Alerts',values.alerts]].forEach(x=>bar.appendChild(item(x[0],x[1]))); const target=document.querySelector('main')||document.querySelector('.jom-main')||document.body; const first=target.querySelector('section,.hero,.command-hero,.page-hero'); if(first&&first.parentNode) first.parentNode.insertBefore(bar,first.nextSibling); else target.insertBefore(bar,target.firstChild); }
  async function init(){ try{ const [summary,alerts,registry]=await Promise.all([getJson(endpoints.summary),getJson(endpoints.alerts),getJson(endpoints.registry)]); insertBar({runtime:runtimeLabel(summary),sources:sourceLabel(summary),registry:registryLabel(registry),discovery:discoveryLabel(registry),alerts:alertLabel(alerts)}); } catch(e){ insertBar({runtime:'Review',sources:'Review',registry:'Unavailable',discovery:'Unavailable',alerts:'Unavailable'}); } }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',init); else init();
})();

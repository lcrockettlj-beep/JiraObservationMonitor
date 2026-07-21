(function(){
  'use strict';
  const siteKey = document.body.getAttribute('data-site-key') || '';
  const $ = id => document.getElementById(id);
  const setText = (id, value) => { const el=$(id); if(el) el.textContent = String(value ?? '-'); };
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  async function getJson(url){ const r=await fetch(url,{cache:'no-store'}); if(!r.ok) throw new Error(url+' '+r.status); return r.json(); }
  async function postJson(url, payload){ const r=await fetch(url,{method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload||{})}); const j=await r.json(); if(!r.ok) throw new Error(j.error||j.message||url+' failed'); return j; }
  async function postDecision(decision){
    const reason = decision === 'approve' ? 'approved for monitoring review' : decision === 'ignore' ? 'not in current monitoring scope' : decision === 'restore' ? 'rolled back to discovered' : 'kept pending review';
    return postJson(`/api/site-review/${encodeURIComponent(siteKey)}/decision`, {decision, reason, actor:'operator'});
  }
  async function enableMonitoring(){ return postJson(`/api/site-review/${encodeURIComponent(siteKey)}/enable-monitoring`, {actor:'operator'}); }
  function link(url){ return url && url !== '-' ? `<a href="${esc(url)}" target="_blank" rel="noopener">${esc(url)}</a>` : '-'; }
  function pill(value){
    const lower=String(value||'').toLowerCase();
    const cls = lower.includes('approve') || lower.includes('monitor') || lower.includes('ok') ? 'review-pill review-pill--ok' : lower.includes('ignore') || lower.includes('blocked') || lower.includes('missing') ? 'review-pill review-pill--risk' : 'review-pill review-pill--warn';
    return `<span class="${cls}">${esc(value)}</span>`;
  }
  function currentState(data){
    const d=String((data.decision_state||{}).decision||'').toLowerCase();
    const s=String(data.lifecycle_status||'').toLowerCase();
    if(d==='monitored' || s==='monitored') return 'monitored';
    if(d==='approve' || s.includes('approval pending')) return 'approval_pending';
    if(d==='ignore' || s==='ignored') return 'ignored';
    if(d==='pending' || s.includes('pending review')) return 'pending';
    return 'discovered';
  }
  function showButton(selector, show){ const el=document.querySelector(selector); if(el) el.style.display=show?'':'none'; }
  function applyButtonFlow(data){
    const state=currentState(data);
    showButton('[data-decision="approve"]', ['discovered','pending','ignored'].includes(state));
    showButton('[data-decision="ignore"]', ['discovered','pending','approval_pending'].includes(state));
    showButton('[data-decision="pending"]', ['discovered','ignored'].includes(state));
    showButton('[data-decision="restore"]', state !== 'discovered');
    showButton('[data-validate-access]', state === 'approval_pending');
    showButton('[data-enable-monitoring]', state === 'approval_pending' || state === 'monitored');
    const enableBtn=document.querySelector('[data-enable-monitoring]');
    if(enableBtn){
      if(state==='monitored') { enableBtn.disabled=true; enableBtn.textContent='Monitoring Enabled'; }
      else { enableBtn.textContent='Enable Monitoring'; }
    }
  }
  function renderHistory(data){
    const host=$('review-decision-history'); if(!host) return;
    const history=Array.isArray(data.decision_history)?data.decision_history:[];
    const current=data.decision_state||{};
    const rows=[];
    if(current.decision){ rows.push(`<article class="review-history-card review-history-current"><strong>Current:</strong> ${pill(current.decision)}<br><span>${esc(current.reason||'No reason recorded')}</span></article>`); }
    const latest = history.slice().reverse().slice(0,5);
    latest.forEach(item=>rows.push(`<article class="review-history-card"><strong>${esc(item.decision)}</strong> <span>${esc(item.decided_at_utc||item.recorded_at_utc||'')}</span><br><span>${esc(item.reason||'')}</span></article>`));
    if(history.length > 5){ rows.push(`<p class="review-muted">Showing latest 5 of ${history.length} lifecycle events.</p>`); }
    host.innerHTML=rows.length?rows.join(''):'<p class="review-muted">No lifecycle decision has been recorded yet.</p>';
  }
  function render(data){
    const site=data.site||{}; const readiness=data.readiness||{}; const decision=data.decision_state||{};
    setText('review-site-title', data.site_name || siteKey);
    const url=data.url||site.site_url||site.url||'-'; const source=Array.isArray(data.sources)?data.sources.join(', '):(data.sources||'Registry');
    const summary=$('review-site-summary'); if(summary) summary.innerHTML=`${link(url)} - source-backed lifecycle review.`;
    setText('review-site-status', data.lifecycle_status || 'Discovered');
    setText('review-status-note', currentState(data)==='monitored' ? 'Monitoring is enabled in JOM. Run refresh to validate live source collection.' : decision.requires_credentials ? 'Approved for monitoring. Validate access before enabling monitoring.' : (decision.decision ? 'Lifecycle decision has been recorded and can be rolled back.' : 'No lifecycle decision has been recorded yet.'));
    setText('review-site-key', data.site_key || siteKey);
    const u=$('review-site-url'); if(u) u.innerHTML=link(url);
    setText('review-site-source', source);
    setText('review-site-classification', data.classification || 'discovered');
    setText('review-site-owner', data.owner || 'Owner not assigned');
    setText('review-site-contact', data.contact_route || 'Reach out via Atlassian/org owner once identified');
    setText('check-identity', readiness.identity || 'Unknown');
    setText('check-ownership', readiness.ownership || 'Owner not assigned');
    setText('check-access', readiness.access || source);
    setText('check-monitoring', readiness.monitoring || 'Not currently monitored');
    setText('check-credential', readiness.credentials || 'Credential required before monitoring enablement');
    renderHistory(data);
    applyButtonFlow(data);
  }
  async function reload(){ const data=await getJson(`/api/site-review/${encodeURIComponent(siteKey)}`); render(data); return data; }
  async function init(){
    await reload();
    document.querySelectorAll('[data-decision]').forEach(button=>button.addEventListener('click', async()=>{
      try{ setText('decision-result','Saving decision...'); const result=await postDecision(button.getAttribute('data-decision')); setText('decision-result', result.message||'Decision recorded.'); await reload(); }
      catch(error){ setText('decision-result','Decision failed: '+error.message); }
    }));
    const enable=document.querySelector('[data-enable-monitoring]');
    if(enable){ enable.addEventListener('click', async()=>{
      try{ setText('decision-result','Enabling monitoring in JOM...'); const result=await enableMonitoring(); setText('decision-result', result.message||'Monitoring enabled. Run runtime refresh to validate live collection.'); await reload(); }
      catch(error){ setText('decision-result','Enable monitoring failed: '+error.message); }
    }); }
  }
  document.addEventListener('DOMContentLoaded',()=>init().catch(error=>{ console.error('Site review failed', error); setText('review-site-title','Site review unavailable'); setText('review-site-summary','Unable to load site review data.'); setText('decision-result','Unable to load site review data: '+error.message); }));
})();

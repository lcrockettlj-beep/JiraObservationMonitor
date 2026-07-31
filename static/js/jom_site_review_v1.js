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
// JOM Site Review Lifecycle Action Controls Alignment v2 START
(function(){
  "use strict";
  const siteKey = document.body.getAttribute("data-site-key") || "";
  const q = (selector) => document.querySelector(selector);
  const show = (el, visible) => { if(el) el.style.display = visible ? "" : "none"; };
  const text = (el, value) => { if(el) el.textContent = value; };
  async function getJson(url){ const r = await fetch(url,{cache:"no-store"}); const j = await r.json().catch(()=>({})); if(!r.ok) throw new Error(j.error || j.message || url + " failed"); return j; }
  async function postJson(url,payload){ const r = await fetch(url,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload||{})}); const j = await r.json().catch(()=>({})); if(!r.ok) throw new Error(j.error || j.message || url + " failed"); return j; }
  function stateOf(data){
    const decision = String((data.decision_state || {}).decision || "").toLowerCase();
    const lifecycle = String(data.lifecycle_status || data.lifecycle || data.classification || "").toLowerCase();
    const monitored = data.is_monitored === true || data.monitored === true || lifecycle === "monitored" || decision === "monitored";
    if(monitored) return "monitored";
    if(decision === "approve" || lifecycle.includes("approval pending")) return "approval_pending";
    if(decision === "ignore" || lifecycle === "ignored") return "ignored";
    return "review";
  }
  function ensureControls(){
    const host = q(".review-decision-actions");
    if(!host) return;
    if(!q("[data-stop-monitoring]")){
      const b = document.createElement("button"); b.type = "button"; b.setAttribute("data-stop-monitoring", "true"); b.textContent = "Stop Monitoring"; host.appendChild(b);
    }
    if(!q("[data-open-site]")){
      const a = document.createElement("a"); a.className = "review-action-link"; a.setAttribute("data-open-site", "true"); a.href = "#"; a.target = "_blank"; a.rel = "noopener noreferrer"; a.textContent = "Open Site"; host.appendChild(a);
    }
  }
  function applyStage(data){
    ensureControls(); const state = stateOf(data || {});
    const approve = q('[data-decision="approve"]'), ignore = q('[data-decision="ignore"]'), pending = q('[data-decision="pending"]'), restore = q('[data-decision="restore"]'), validate = q('[data-validate-access]'), enable = q('[data-enable-monitoring]'), stop = q('[data-stop-monitoring]'), open = q('[data-open-site]');
    const url = data && (data.url || data.site_url || (data.site || {}).site_url || (data.site || {}).url);
    if(open){ open.href = url || "#"; show(open, !!url); }
    show(approve, state === "review"); show(ignore, state === "review" || state === "approval_pending"); show(pending, state === "review"); show(restore, state === "approval_pending" || state === "ignored"); show(validate, state === "approval_pending"); show(enable, state === "approval_pending"); show(stop, state === "monitored");
    if(validate) text(validate, "Start Atlassian Authorization"); if(enable) text(enable, "Enable Monitoring"); if(stop) text(stop, "Stop Monitoring"); if(restore) text(restore, state === "ignored" ? "Restore to Review" : "Return to Review");
    const help = document.getElementById("decision-help");
    if(help){ help.textContent = state === "approval_pending" ? "Approval is recorded. Start Atlassian authorization, validate access, then enable monitoring." : state === "monitored" ? "Monitoring is enabled. Stop monitoring if this site should leave the monitored registry." : state === "ignored" ? "This site is ignored from current scope. Restore it to review before taking monitoring action." : "Review this authenticated discovery. Approve for monitoring or ignore it from current scope."; }
  }
  async function refreshStage(){ try{ const data = await getJson(`/api/site-review/${encodeURIComponent(siteKey)}`); applyStage(data); }catch(_error){ ensureControls(); } }
  async function stopMonitoring(){ const result = document.getElementById("decision-result"); try{ text(result, "Stopping monitoring..."); const payload = await postJson(`/api/site-review/${encodeURIComponent(siteKey)}/stop-monitoring`, {actor:"operator", reason:"stopped from Site Review"}); text(result, payload.message || "Monitoring stopped."); await refreshStage(); }catch(error){ text(result, "Stop monitoring failed: " + error.message); } }
  function wire(){ ensureControls(); const stop = q('[data-stop-monitoring]'); if(stop && !stop.dataset.stopMonitoringWired){ stop.dataset.stopMonitoringWired = "true"; stop.addEventListener("click", stopMonitoring); } document.querySelectorAll("[data-decision], [data-enable-monitoring], [data-validate-access]").forEach((el)=>{ if(!el.dataset.lifecycleRefreshWired){ el.dataset.lifecycleRefreshWired = "true"; el.addEventListener("click", ()=>{ setTimeout(refreshStage,900); setTimeout(refreshStage,1800); }); } }); refreshStage(); let attempts=0; const timer=setInterval(()=>{ attempts += 1; refreshStage(); if(attempts>=8) clearInterval(timer); },400); window.addEventListener("focus",()=>setTimeout(refreshStage,500)); }
  if(document.readyState === "loading") document.addEventListener("DOMContentLoaded", wire); else wire();
}());
// JOM Site Review Lifecycle Action Controls Alignment v2 END
// JOM Site Review Visual Polish and Wording v1 START
(function(){
  "use strict";
  function q(selector){ return document.querySelector(selector); }
  function text(el, value){ if(el) el.textContent = value; }
  function normalise(value){ return String(value || "").trim().toLowerCase(); }
  function prettyStatus(raw){
    const value = normalise(raw);
    if(value === "registered review" || value === "registered_review") return "Review Required";
    if(value === "pending review" || value === "pending_review") return "Pending Review";
    if(value === "approval pending" || value === "approval_pending") return "Approval Pending";
    if(value === "monitored") return "Monitored";
    if(value === "ignored") return "Ignored";
    return raw || "Review Required";
  }
  function polishStatus(){
    const status = document.getElementById("review-site-status");
    if(status) text(status, prettyStatus(status.textContent));
  }
  function polishValidationCopy(){
    const validation = document.getElementById("site-review-validation-status");
    if(!validation) return;
    const current = normalise(validation.textContent);
    if(current.includes("credential access has not been validated")){
      validation.textContent = "Access has not been validated yet. Start Atlassian authorization before enabling monitoring.";
    }
    if(current.includes("access validation required before monitoring can be enabled")){
      validation.textContent = "Access validation is required before monitoring can be enabled. Start Atlassian authorization when ready.";
    }
  }
  function polishDecisionResult(){
    const result = document.getElementById("decision-result");
    if(result && normalise(result.textContent).includes("no decision submitted")){
      result.textContent = "No lifecycle action has been submitted in this session.";
    }
  }
  function polishButtons(){
    const validate = q('[data-validate-access]');
    if(validate) validate.textContent = "Start Atlassian Authorization";
    const pending = q('[data-decision="pending"]');
    if(pending) pending.textContent = "Keep in Review";
    const approve = q('[data-decision="approve"]');
    if(approve) approve.textContent = "Approve for Monitoring";
    const ignore = q('[data-decision="ignore"]');
    if(ignore) ignore.textContent = "Ignore for Now";
  }
  function polish(){
    polishStatus();
    polishValidationCopy();
    polishDecisionResult();
    polishButtons();
  }
  if(document.readyState === "loading") document.addEventListener("DOMContentLoaded", polish);
  else polish();
  let attempts = 0;
  const timer = setInterval(function(){
    attempts += 1;
    polish();
    if(attempts >= 10) clearInterval(timer);
  }, 400);
  window.addEventListener("focus", function(){ setTimeout(polish, 300); });
}());
// JOM Site Review Visual Polish and Wording v1 END

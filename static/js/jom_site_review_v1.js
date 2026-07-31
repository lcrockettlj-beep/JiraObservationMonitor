(function(){
  'use strict';

  const siteKey = document.body.getAttribute('data-site-key') || '';
  const $ = (id) => document.getElementById(id);
  const setText = (id, value) => { const el = $(id); if (el) el.textContent = String(value ?? '-'); };
  const esc = (value) => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[ch]));

  let currentReviewData = null;
  let validationState = null;

  async function getJson(url){
    const r = await fetch(url,{cache:'no-store'});
    const j = await r.json().catch(() => ({}));
    if(!r.ok) throw new Error(j.error || j.message || url + ' failed');
    return j;
  }

  async function postJson(url, payload){
    const r = await fetch(url,{method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload || {})});
    const j = await r.json().catch(() => ({}));
    if(!r.ok && !j.authorization_url) throw new Error(j.error || j.message || url + ' failed');
    return j;
  }

  function link(url){
    return url && url !== '-' ? '<a href="' + esc(url) + '" target="_blank" rel="noopener noreferrer">' + esc(url) + '</a>' : '-';
  }

  function pill(value){
    const lower = String(value || '').toLowerCase();
    const cls = lower.includes('approve') || lower.includes('monitor') || lower.includes('ok') ? 'review-pill review-pill--ok' : lower.includes('ignore') || lower.includes('blocked') || lower.includes('missing') ? 'review-pill review-pill--risk' : 'review-pill review-pill--warn';
    return '<span class="' + cls + '">' + esc(value) + '</span>';
  }

  function stageOf(data){
    const decision = String((data.decision_state || {}).decision || '').toLowerCase();
    const lifecycle = String(data.lifecycle_status || data.lifecycle || data.classification || '').toLowerCase();
    const monitored = data.is_monitored === true || data.monitored === true || lifecycle === 'monitored' || lifecycle.includes('monitoring enabled') || decision === 'monitored';
    if(monitored) return 'monitored';
    if(decision === 'ignore' || decision === 'ignored' || lifecycle.includes('ignored')) return 'ignored';
    if(decision === 'approve' || decision === 'approved' || lifecycle.includes('approval pending') || lifecycle.includes('registered review') || lifecycle.includes('pending review')) return 'approval_pending';
    return 'review';
  }

  function accessValid(){
    if(!validationState) return false;
    return validationState.access_valid === true || validationState.status === 'ok';
  }

  function show(selector, visible){
    const el = document.querySelector(selector);
    if(!el) return;
    el.hidden = !visible;
    el.setAttribute('aria-hidden', visible ? 'false' : 'true');
    if(visible){
      el.style.removeProperty('display');
    } else {
      el.style.setProperty('display', 'none', 'important');
    }
  }

  function setValidationText(text, state){
    const el = $('site-review-validation-status');
    if(!el) return;
    el.textContent = text;
    if(state) el.setAttribute('data-state', state);
  }

  function applyButtonFlow(data){
    const stage = stageOf(data);
    const valid = accessValid();

    show('[data-decision="approve"]', stage === 'review');
    show('[data-decision="ignore"]', stage === 'review');
    show('[data-decision="pending"]', stage === 'review');
    show('[data-decision="restore"]', stage === 'approval_pending' || stage === 'ignored');
    show('[data-start-auth]', stage === 'approval_pending' && !valid);
    show('[data-enable-monitoring]', stage === 'approval_pending' && valid);
    show('[data-stop-monitoring]', stage === 'monitored');
    show('[data-open-site]', true);

    const restore = document.querySelector('[data-decision="restore"]');
    if(restore) restore.textContent = stage === 'ignored' ? 'Restore to Review' : 'Return to Review';

    const open = document.querySelector('[data-open-site]');
    const url = data.url || data.site_url || (data.site || {}).site_url || (data.site || {}).url || '';
    if(open){ open.href = url || '#'; open.style.display = url ? '' : 'none'; }

    const ignored = $('review-ignored-panel');
    if(ignored) ignored.hidden = stage !== 'ignored';

    if(stage === 'review') setValidationText('Review this discovery. Approve it for monitoring, ignore it, or keep it in review.', 'review');
    if(stage === 'approval_pending' && !valid) setValidationText('Approval recorded. Start Atlassian Authorization before monitoring can be enabled.', 'blocked');
    if(stage === 'approval_pending' && valid) setValidationText('Access validated. Enable Monitoring is now available.', 'ok');
    if(stage === 'monitored') setValidationText('Monitoring is enabled for this site.', 'ok');
    if(stage === 'ignored') setValidationText('This site is ignored from current monitoring scope.', 'review');
  }

  function renderHistory(data){
    const host = $('review-decision-history');
    if(!host) return;
    const history = Array.isArray(data.decision_history) ? data.decision_history : [];
    const current = data.decision_state || {};
    const rows = [];
    if(current.decision){
      rows.push('<div class="review-history-card review-history-current"><strong>Current: ' + pill(current.decision) + '</strong><br>' + esc(current.reason || 'No reason recorded') + '</div>');
    }
    history.slice().reverse().slice(0,5).forEach(item => {
      rows.push('<div class="review-history-card"><strong>' + esc(item.decision) + '</strong> <span>' + esc(item.decided_at_utc || item.recorded_at_utc || '') + '</span><br>' + esc(item.reason || '') + '</div>');
    });
    host.innerHTML = rows.length ? rows.join('') : '<p class="review-muted">No lifecycle decision has been recorded yet.</p>';
  }

  function render(data){
    currentReviewData = data;
    const site = data.site || {};
    const readiness = data.readiness || {};
    const decision = data.decision_state || {};
    const url = data.url || site.site_url || site.url || '-';
    const stage = stageOf(data);

    setText('review-site-title', data.site_name || data.site_key || siteKey);
    const summary = $('review-site-summary');
    if(summary) summary.innerHTML = link(url) + ' - source-backed lifecycle review.';
    setText('review-site-status', data.lifecycle_status || (stage === 'review' ? 'Review Required' : stage));
    setText('review-status-note', stage === 'monitored' ? 'Monitoring is enabled in JOM. Run refresh to validate live source collection.' : decision.requires_credentials ? 'Approved for monitoring. Start Atlassian Authorization before enabling monitoring.' : (decision.decision ? 'Lifecycle decision has been recorded and can be rolled back.' : 'No lifecycle decision has been recorded yet.'));
    setText('review-site-key', data.site_key || siteKey);
    const urlNode = $('review-site-url');
    if(urlNode) urlNode.innerHTML = link(url);
    setText('review-site-owner', data.owner || 'Owner not assigned');
    setText('review-site-contact', data.contact_route || 'Owner/contact not yet sourced');
    renderHistory(data);
    applyButtonFlow(data);
  }

  async function loadValidation(){
    try{
      const payload = await getJson('/api/site-review/' + encodeURIComponent(siteKey) + '/access-validation');
      validationState = payload.validation || {};
    } catch(_error){
      validationState = {};
    }
  }

  async function reload(){
    await loadValidation();
    const data = await getJson('/api/site-review/' + encodeURIComponent(siteKey));
    render(data);
    return data;
  }

  async function postDecision(decision){
    const reason = decision === 'approve' ? 'approved for monitoring review' : decision === 'ignore' ? 'not in current monitoring scope' : decision === 'restore' ? 'rolled back to review' : 'kept pending review';
    return postJson('/api/site-review/' + encodeURIComponent(siteKey) + '/decision', {decision, reason, actor:'operator'});
  }

  async function startAuthorization(){
    setValidationText('Preparing Atlassian authorization link...', 'pending');
    let payload = await getJson('/api/oauth/authorize-url/' + encodeURIComponent(siteKey));
    if(!payload.authorization_url){
      payload = await postJson('/api/site-review/' + encodeURIComponent(siteKey) + '/validate-access', {actor:'operator'});
    }
    if(payload.authorization_url){
      window.open(payload.authorization_url, '_blank', 'noopener,noreferrer');
      setValidationText('Atlassian authorization started. Complete authorization, then return to this page so JOM can validate access.', 'pending');
      return;
    }
    if(payload.validation && payload.validation.access_valid === true){
      validationState = payload.validation;
      setValidationText('Access validated. Enable Monitoring is now available.', 'ok');
      if(currentReviewData) applyButtonFlow(currentReviewData);
      return;
    }
    setValidationText(payload.message || payload.reason || 'Authorization URL is unavailable. Check OAuth configuration.', 'blocked');
  }

  async function completeOAuth(){
    try{
      const payload = await postJson('/api/site-review/' + encodeURIComponent(siteKey) + '/oauth-complete', {actor:'site-review-return'});
      if(payload && payload.ok && payload.validation){
        validationState = payload.validation;
        setValidationText('Access validated from Atlassian authorization. Enable Monitoring is now available.', 'ok');
        if(currentReviewData) applyButtonFlow(currentReviewData);
      }
    } catch(_error){ }
  }

  async function enableMonitoring(){ return postJson('/api/site-review/' + encodeURIComponent(siteKey) + '/enable-monitoring', {actor:'operator'}); }
  async function stopMonitoring(){ return postJson('/api/site-review/' + encodeURIComponent(siteKey) + '/stop-monitoring', {actor:'operator', reason:'stopped from Site Review'}); }

  async function init(){
    await reload();
    document.querySelectorAll('[data-decision]').forEach(button => button.addEventListener('click', async () => {
      try{
        setText('decision-result','Saving decision...');
        const result = await postDecision(button.getAttribute('data-decision'));
        setText('decision-result', result.message || 'Decision recorded.');
        await reload();
      }catch(error){ setText('decision-result','Decision failed: ' + error.message); }
    }));
    const auth = document.querySelector('[data-start-auth]');
    if(auth) auth.addEventListener('click', async () => { try{ await startAuthorization(); }catch(error){ setValidationText('Atlassian authorization could not start: ' + error.message, 'failed'); } });
    const enable = document.querySelector('[data-enable-monitoring]');
    if(enable) enable.addEventListener('click', async () => { try{ setText('decision-result','Enabling monitoring in JOM...'); const result = await enableMonitoring(); setText('decision-result', result.message || 'Monitoring enabled.'); await reload(); }catch(error){ setText('decision-result','Enable monitoring failed: ' + error.message); } });
    const stop = document.querySelector('[data-stop-monitoring]');
    if(stop) stop.addEventListener('click', async () => { try{ setText('decision-result','Stopping monitoring...'); const result = await stopMonitoring(); setText('decision-result', result.message || 'Monitoring stopped.'); await reload(); }catch(error){ setText('decision-result','Stop monitoring failed: ' + error.message); } });
    window.addEventListener('focus', () => setTimeout(() => { completeOAuth(); reload(); }, 600));
  }

  document.addEventListener('DOMContentLoaded', () => init().catch(error => {
    console.error('Site review failed', error);
    setText('review-site-title', siteKey || 'Site review unavailable');
    setText('review-site-summary', 'Unable to load site review data.');
    setText('decision-result', 'Unable to load site review data: ' + error.message);
  }));
})();

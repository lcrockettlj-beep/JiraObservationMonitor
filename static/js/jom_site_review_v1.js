(function(){
  'use strict';
  const siteKey = document.body.getAttribute('data-site-key') || '';
  const $ = id => document.getElementById(id);
  const setText = (id, value) => { const el = $(id); if (el) el.textContent = String(value ?? '-'); };
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));

  async function getJson(url){ const r = await fetch(url,{cache:'no-store'}); const j = await r.json().catch(()=>({})); if(!r.ok) throw new Error(j.error || j.message || url + ' failed'); return j; }
  async function postJson(url, payload){ const r = await fetch(url,{method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload || {})}); const j = await r.json().catch(()=>({})); if(!r.ok) throw new Error(j.error || j.message || url + ' failed'); return j; }

  function link(url){ return url && url !== '-' ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(url)}</a>` : '-'; }
  function pill(value){ const lower = String(value || '').toLowerCase(); const cls = lower.includes('approve') || lower.includes('monitor') || lower.includes('ok') ? 'review-pill review-pill--ok' : lower.includes('ignore') || lower.includes('blocked') || lower.includes('missing') ? 'review-pill review-pill--risk' : 'review-pill review-pill--warn'; return `<span class="${cls}">${esc(value)}</span>`; }

  function stateOf(data){
    const decision = String((data.decision_state || {}).decision || '').toLowerCase();
    const lifecycle = String(data.lifecycle_status || data.lifecycle || data.classification || '').toLowerCase();
    const monitored = data.is_monitored === true || data.monitored === true || lifecycle === 'monitored' || decision === 'monitored';
    if (monitored) return 'monitored';
    if (decision === 'approve' || lifecycle.includes('approval pending')) return 'approval_pending';
    if (decision === 'ignore' || lifecycle === 'ignored') return 'ignored';
    return 'review';
  }

  function ensureControls(){
    const host = document.querySelector('.review-decision-actions');
    if (!host) return;
    if (!document.querySelector('[data-stop-monitoring]')) {
      const b = document.createElement('button'); b.type = 'button'; b.setAttribute('data-stop-monitoring','true'); b.textContent = 'Stop Monitoring'; host.appendChild(b);
    }
    if (!document.querySelector('[data-open-site]')) {
      const a = document.createElement('a'); a.className = 'review-action-link'; a.setAttribute('data-open-site','true'); a.href = '#'; a.target = '_blank'; a.rel = 'noopener noreferrer'; a.textContent = 'Open Site'; host.appendChild(a);
    }
  }

  function show(selector, visible){ const el = document.querySelector(selector); if (el) el.style.display = visible ? '' : 'none'; }

  function applyButtonFlow(data){
    ensureControls();
    const state = stateOf(data);
    show('[data-decision="approve"]', state === 'review');
    show('[data-decision="ignore"]', state === 'review' || state === 'approval_pending');
    show('[data-decision="pending"]', state === 'review');
    show('[data-decision="restore"]', state === 'approval_pending' || state === 'ignored');
    show('[data-validate-access]', state === 'approval_pending');
    show('[data-enable-monitoring]', state === 'approval_pending');
    show('[data-stop-monitoring]', state === 'monitored');

    const open = document.querySelector('[data-open-site]');
    const url = data.url || data.site_url || (data.site || {}).site_url || (data.site || {}).url || '';
    if (open) { open.href = url || '#'; open.style.display = url ? '' : 'none'; }

    const validate = document.querySelector('[data-validate-access]'); if (validate) validate.textContent = 'Start Atlassian Authorization';
    const pending = document.querySelector('[data-decision="pending"]'); if (pending) pending.textContent = 'Keep in Review';
    const restore = document.querySelector('[data-decision="restore"]'); if (restore) restore.textContent = state === 'ignored' ? 'Restore to Review' : 'Return to Review';
    const help = $('decision-help');
    if (help) {
      help.textContent = state === 'monitored'
        ? 'Monitoring is enabled. Stop monitoring if this site should leave the monitored registry.'
        : state === 'approval_pending'
          ? 'Approval is recorded. Start Atlassian authorization, validate access, then enable monitoring.'
          : state === 'ignored'
            ? 'This site is ignored from current scope. Restore it to review before taking monitoring action.'
            : 'Review this authenticated discovery. Approve for monitoring or ignore it from current scope.';
    }
  }

  function renderHistory(data){
    const host = $('review-decision-history'); if (!host) return;
    const history = Array.isArray(data.decision_history) ? data.decision_history : [];
    const current = data.decision_state || {};
    const rows = [];
    if (current.decision) rows.push(`<div class="review-history-card review-history-current"><strong>Current: ${pill(current.decision)}</strong><br><span>${esc(current.reason || 'No reason recorded')}</span></div>`);
    history.slice().reverse().slice(0,5).forEach(item => rows.push(`<div class="review-history-card"><strong>${esc(item.decision)}</strong> <span>${esc(item.decided_at_utc || item.recorded_at_utc || '')}</span><br><span>${esc(item.reason || '')}</span></div>`));
    host.innerHTML = rows.length ? rows.join('') : '<p>No lifecycle decision has been recorded yet.</p>';
  }

  function render(data){
    const site = data.site || {};
    const readiness = data.readiness || {};
    const decision = data.decision_state || {};
    const url = data.url || site.site_url || site.url || '-';
    setText('review-site-title', data.site_name || data.site_key || siteKey);
    const summary = $('review-site-summary'); if (summary) summary.innerHTML = `${link(url)} - source-backed lifecycle review.`;
    setText('review-site-status', data.lifecycle_status || 'Review Required');
    setText('review-status-note', stateOf(data) === 'monitored' ? 'Monitoring is enabled in JOM. Run refresh to validate live source collection.' : decision.requires_credentials ? 'Approved for monitoring. Validate access before enabling monitoring.' : (decision.decision ? 'Lifecycle decision has been recorded and can be rolled back.' : 'No lifecycle decision has been recorded yet.'));
    setText('review-site-key', data.site_key || siteKey);
    const u = $('review-site-url'); if (u) u.innerHTML = link(url);
    setText('review-site-owner', data.owner || 'Owner not assigned');
    setText('review-site-contact', data.contact_route || 'Owner/contact not yet sourced');
    setText('check-identity', readiness.identity || 'Unknown');
    setText('check-ownership', readiness.ownership || 'Owner not assigned');
    setText('check-access', readiness.access || 'Source-backed');
    setText('check-monitoring', readiness.monitoring || 'Not currently monitored');
    setText('check-credential', readiness.credentials || 'Credential required before monitoring enablement');
    renderHistory(data);
    applyButtonFlow(data);
  }

  async function reload(){ const data = await getJson(`/api/site-review/${encodeURIComponent(siteKey)}`); render(data); return data; }
  async function postDecision(decision){ const reason = decision === 'approve' ? 'approved for monitoring review' : decision === 'ignore' ? 'not in current monitoring scope' : decision === 'restore' ? 'rolled back to discovered' : 'kept pending review'; return postJson(`/api/site-review/${encodeURIComponent(siteKey)}/decision`, {decision, reason, actor:'operator'}); }
  async function enableMonitoring(){ return postJson(`/api/site-review/${encodeURIComponent(siteKey)}/enable-monitoring`, {actor:'operator'}); }
  async function stopMonitoring(){ return postJson(`/api/site-review/${encodeURIComponent(siteKey)}/stop-monitoring`, {actor:'operator', reason:'stopped from Site Review'}); }

  async function init(){
    ensureControls();
    await reload();
    document.querySelectorAll('[data-decision]').forEach(button => button.addEventListener('click', async () => { try { setText('decision-result','Saving decision...'); const result = await postDecision(button.getAttribute('data-decision')); setText('decision-result', result.message || 'Decision recorded.'); await reload(); } catch(error){ setText('decision-result','Decision failed: ' + error.message); } }));
    const enable = document.querySelector('[data-enable-monitoring]'); if (enable) enable.addEventListener('click', async () => { try { setText('decision-result','Enabling monitoring in JOM...'); const result = await enableMonitoring(); setText('decision-result', result.message || 'Monitoring enabled.'); await reload(); } catch(error){ setText('decision-result','Enable monitoring failed: ' + error.message); } });
    const stop = document.querySelector('[data-stop-monitoring]'); if (stop) stop.addEventListener('click', async () => { try { setText('decision-result','Stopping monitoring...'); const result = await stopMonitoring(); setText('decision-result', result.message || 'Monitoring stopped.'); await reload(); } catch(error){ setText('decision-result','Stop monitoring failed: ' + error.message); } });
    window.addEventListener('focus', () => setTimeout(reload, 500));
  }

  document.addEventListener('DOMContentLoaded', () => init().catch(error => { console.error('Site review failed', error); setText('review-site-title','Site review unavailable'); setText('review-site-summary','Unable to load site review data.'); setText('decision-result','Unable to load site review data: ' + error.message); }));
}());

(function(){
  'use strict';
  const siteKey = document.body.getAttribute('data-site-key') || '';
  const $ = id => document.getElementById(id);
  const setText = (id, value) => { const el=$(id); if(el) el.textContent = String(value ?? '-'); };
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  async function getJson(url){ const r=await fetch(url,{cache:'no-store'}); if(!r.ok) throw new Error(url+' '+r.status); return r.json(); }
  async function postDecision(decision){
    const reason = decision === 'approve' ? 'approved for monitoring review' : decision === 'ignore' ? 'not in current monitoring scope' : decision === 'restore' ? 'restored to review queue' : 'kept pending review';
    const r = await fetch(`/api/site-review/${encodeURIComponent(siteKey)}/decision`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({decision, reason, actor:'operator'})});
    const payload = await r.json();
    if(!r.ok) throw new Error(payload.error || payload.message || 'Decision failed');
    return payload;
  }
  function link(url){ return url && url !== '-' ? `<a href="${esc(url)}" target="_blank" rel="noopener">${esc(url)}</a>` : '-'; }
  function pill(value){
    const lower=String(value||'').toLowerCase();
    const cls = lower.includes('approve') || lower.includes('monitored') || lower.includes('ok') ? 'review-pill review-pill--ok' : lower.includes('ignore') || lower.includes('blocked') || lower.includes('missing') ? 'review-pill review-pill--risk' : 'review-pill review-pill--warn';
    return `<span class="${cls}">${esc(value)}</span>`;
  }
  function renderHistory(data){
    const host=$('review-decision-history'); if(!host) return;
    const history = Array.isArray(data.decision_history) ? data.decision_history : [];
    const current = data.decision_state || {};
    const rows = [];
    if(current.decision){ rows.push(`<article class="review-history-card"><strong>Current decision:</strong> ${pill(current.decision)}<br><span>${esc(current.reason || 'No reason recorded')}</span></article>`); }
    history.slice().reverse().forEach(item => rows.push(`<article class="review-history-card"><strong>${esc(item.decision)}</strong> by ${esc(item.actor || 'operator')}<br><span>${esc(item.decided_at_utc || item.recorded_at_utc || '')}</span><br><span>${esc(item.reason || '')}</span></article>`));
    host.innerHTML = rows.length ? rows.join('') : '<p class="review-muted">No lifecycle decision has been recorded yet.</p>';
  }
  function render(data){
    const site = data.site || {};
    const readiness = data.readiness || {};
    const decision = data.decision_state || {};
    setText('review-site-title', data.site_name || siteKey);
    const url = data.url || site.site_url || site.url || '-';
    const source = Array.isArray(data.sources) ? data.sources.join(', ') : (data.sources || 'Registry');
    $('review-site-summary').innerHTML = `${link(url)} - source-backed lifecycle review.`;
    setText('review-site-status', data.lifecycle_status || 'Discovered');
    setText('review-status-note', decision.requires_credentials ? 'Approved for monitoring but credentials/tokens are still required before monitoring can be enabled.' : (decision.decision ? 'Lifecycle decision has been recorded and can be changed.' : 'No lifecycle decision has been recorded yet.'));
    setText('review-site-key', data.site_key || siteKey);
    $('review-site-url').innerHTML = link(url);
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
  }
  async function init(){
    const data = await getJson(`/api/site-review/${encodeURIComponent(siteKey)}`);
    render(data);
    document.querySelectorAll('[data-decision]').forEach(button => {
      button.addEventListener('click', async () => {
        const decision = button.getAttribute('data-decision');
        try{
          setText('decision-result','Saving decision...');
          const result = await postDecision(decision);
          setText('decision-result', result.message || 'Decision recorded.');
          const updated = await getJson(`/api/site-review/${encodeURIComponent(siteKey)}`);
          render(updated);
        }catch(error){ setText('decision-result','Decision failed: '+error.message); }
      });
    });
  }
  document.addEventListener('DOMContentLoaded', () => init().catch(error => {
    console.error('Site review failed', error);
    setText('review-site-title','Site review unavailable');
    setText('review-site-summary','Unable to load site review data.');
    setText('decision-result','Unable to load site review data: '+error.message);
  }));
})();

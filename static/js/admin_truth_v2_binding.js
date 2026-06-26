(function () {
  function n(v){ const x=Number(v||0); return Number.isFinite(x)?x:0; }
  function fmt(v){ return n(v).toLocaleString(); }
  function text(id,val){ const el=document.getElementById(id); if(el) el.textContent=val; }
  function badge(status){ return status==='aligned'?'Aligned':status||'Unknown'; }
  function severityClass(sev){ return sev==='ok'?'truth-badge--ok':(sev==='critical'?'truth-badge--critical':'truth-badge--warning'); }
  function panel(rootId,title,sub){
    let root=document.getElementById(rootId); if(!root) return null;
    if(document.getElementById(rootId+'-card')) return document.getElementById(rootId+'-card');
    const card=document.createElement('section'); card.id=rootId+'-card'; card.className='admin-truth-v2-card signal-border';
    card.innerHTML=`<div class="admin-truth-v2-head"><div><h2>${title}</h2><p>${sub}</p></div><span class="truth-badge" id="${rootId}-status">Loading</span></div>
    <div class="admin-truth-v2-grid">
      <div class="truth-mini"><span>Human users</span><strong id="${rootId}-humans">--</strong><small>Admin identity truth</small></div>
      <div class="truth-mini"><span>Billing seats</span><strong id="${rootId}-billing">--</strong><small>Commercial truth</small></div>
      <div class="truth-mini"><span>API product users</span><strong id="${rootId}-api">--</strong><small>Application role count</small></div>
      <div class="truth-mini"><span>Variance</span><strong id="${rootId}-variance">--</strong><small>API minus billing</small></div>
      <div class="truth-mini"><span>Ratio</span><strong id="${rootId}-ratio">--</strong><small>Seats per human</small></div>
      <div class="truth-mini"><span>Confirmed sites</span><strong id="${rootId}-sites">--</strong><small>Product access confirmed</small></div>
    </div>
    <p class="admin-truth-v2-insight" id="${rootId}-insight">Waiting for Admin Truth Layer v2.</p>
    <p class="admin-truth-v2-guard" id="${rootId}-guard">Named user-to-site footprint remains hidden until a Directory-equivalent source is verified.</p>`;
    const anchor = root.querySelector('.section-header') || root.firstElementChild;
    if(anchor && anchor.nextSibling) root.insertBefore(card, anchor.nextSibling); else root.appendChild(card);
    return card;
  }
  function apply(rootId,p){
    const s=(p&&p.summary)||{}; const controls=(p&&p.controls)||{};
    const status=document.getElementById(rootId+'-status');
    if(status){ status.textContent=badge(s.status); status.className='truth-badge '+severityClass(s.severity); }
    text(rootId+'-humans',fmt(s.admin_human_users));
    text(rootId+'-billing',fmt(s.billing_jira_seats));
    text(rootId+'-api',fmt(s.api_product_users));
    text(rootId+'-variance',String(n(s.api_minus_billing)));
    text(rootId+'-ratio',Number(s.billing_to_human_ratio||0).toFixed(2));
    text(rootId+'-sites',`${fmt(s.confirmed_product_site_count)} / ${fmt(s.accessible_jira_resource_count)}`);
    text(rootId+'-insight',s.interpretation||'Admin Truth Layer v2 is available.');
    text(rootId+'-guard',controls.named_user_footprint_guard_reason||'Named user-to-site footprint remains hidden until verified.');
  }
  function init(){
    const adminRoot=document.querySelector('body');
    const estateRoot=document.getElementById('estate-trust-intelligence')||document.querySelector('body');
    const isAdmin=location.pathname.indexOf('/admin')===0;
    const isEstate=location.pathname.indexOf('/estate')===0;
    if(!isAdmin && !isEstate) return;
    const rootId=isAdmin?'admin-truth-v2':'estate-admin-truth-v2';
    const containerId=rootId+'-mount';
    let mount=document.getElementById(containerId);
    if(!mount){ mount=document.createElement('div'); mount.id=containerId; (isEstate?estateRoot:adminRoot).appendChild(mount); }
    panel(containerId,'Admin Truth Layer v2','Verified comparison between Admin identity, Atlassian billing, and Jira API product access.');
    fetch('/static/data/admin_truth_v2.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error('missing');return r.json();}).then(p=>apply(containerId,p)).catch(()=>{});
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',init); else init();
})();

(function(){
  'use strict';
  function text(el){ return (el && el.textContent ? el.textContent : '').replace(/\s+/g,' ').trim(); }
  function hide(el){ if(el) el.classList.add('jom-hidden-by-cleanup-v1'); }
  function closestCard(el){ return el && (el.closest('section') || el.closest('article') || el.closest('.jom-card') || el.closest('.review-panel') || el.closest('.site-card') || el.closest('.card')); }
  function numberText(value){
    const m=String(value||'').match(/-?\d+/);
    return m ? Number(m[0]) : null;
  }
  function hideRailRowsByLabel(labels){
    const wanted=labels.map(x=>x.toLowerCase());
    document.querySelectorAll('dt').forEach(dt=>{
      const label=text(dt).toLowerCase();
      if(!wanted.includes(label)) return;
      const row=dt.closest('div');
      const val=text(row && row.querySelector('dd'));
      if(!val || val.toLowerCase()==='n/a' || val==='0') hide(row);
    });
  }
  function hideEstateEmptyQueue(){
    const page=document.body.getAttribute('data-jom-page');
    if(page!=='estate') return;
    const count=text(document.getElementById('estate-review-count')).toLowerCase();
    const list=text(document.getElementById('estate-review-list')).toLowerCase();
    const isEmpty=(count.includes('0') || count==='--') && (list.includes('no discovered sites') || list.includes('0 review') || !list);
    if(isEmpty){ hide(document.getElementById('discovered-sites')); }
  }
  function hideCardsContaining(phrases){
    const phraseList=phrases.map(p=>p.toLowerCase());
    document.querySelectorAll('section, article, .jom-card, .site-card, .card, .panel').forEach(card=>{
      const body=text(card).toLowerCase();
      if(phraseList.some(p=>body.includes(p))) hide(card);
    });
  }
  function hideSignalRowsContaining(phrases){
    const phraseList=phrases.map(p=>p.toLowerCase());
    document.querySelectorAll('li, .site-signal-card, .jom-risk-item, .review-history-card').forEach(row=>{
      const body=text(row).toLowerCase();
      if(phraseList.some(p=>body.includes(p))) hide(row);
    });
  }
  function hideSiteWorkspaceNoise(){
    const page=document.body.getAttribute('data-jom-page') || '';
    const isSite=page.includes('site') || location.pathname.startsWith('/site/');
    if(!isSite) return;

    // Top readiness/status strip and duplicate navigation/action banner.
    hideCardsContaining([
      'site workspace readiness',
      'live source-backed status across runtime',
      'export planned'
    ]);

    // Duplicate/low-value KPI tiles. Product/users/access tiles remain.
    document.querySelectorAll('article, section, .site-kpi, .kpi-card, .metric-card, .jom-card, .card').forEach(card=>{
      const body=text(card).toLowerCase();
      if(body.includes('monitoring state') || body.includes('operational risk') || body.includes('last refresh')) hide(card);
    });

    // Empty placeholder panel until projects are source-backed.
    hideCardsContaining([
      'storage / projects / automation',
      'reserved for source-backed project',
      'reserved for source-backed project, storage and automation signals'
    ]);

    // Remove source-state warning line when it is just estate-wide review noise.
    hideSignalRowsContaining(['source state: review']);

    // Remove report footer links on Site Workspace.
    document.querySelectorAll('section, article, div').forEach(el=>{
      const body=text(el).toLowerCase();
      if(body === 'reports html csv json' || (body.startsWith('reports ') && body.includes(' html ') && body.includes(' csv ') && body.includes(' json'))) hide(el);
    });
  }
  function run(){
    hideRailRowsByLabel(['Users']);
    hideEstateEmptyQueue();
    hideSiteWorkspaceNoise();
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', run); else run();
  [250,750,1500,3000].forEach(t=>setTimeout(run,t));
})();

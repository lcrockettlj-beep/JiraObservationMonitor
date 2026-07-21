(function(){
  'use strict';
  function text(el){ return (el && el.textContent ? el.textContent : '').replace(/\s+/g,' ').trim(); }
  function hide(el){ if(el) el.classList.add('jom-site-workspace-clean-hidden'); }
  function isSiteWorkspace(){ return location.pathname.startsWith('/site/') || (document.body.getAttribute('data-jom-page') || '') === 'site-workspace'; }
  function hideReportBars(){
    document.querySelectorAll('[data-jom-export-reporting="v1"], .jom-export-reporting-actions').forEach(hide);
    document.querySelectorAll('section, article, div, footer').forEach(el => {
      const compact=text(el).toLowerCase();
      if(compact === 'reports html csv json' || compact.startsWith('reports html csv json')) hide(el);
    });
  }
  function hideEmptyProductAccess(){
    const tbody=document.getElementById('site-product-access-body');
    if(!tbody) return;
    const body=text(tbody).toLowerCase();
    const empty = body.includes('no source-backed product access currently available') || body.includes('no product-access rows available') || body.includes('has not yet produced product-access data') || body.includes('no product-access match') || body === 'loading...' || body.includes('unavailable');
    if(empty){ hide(document.getElementById('site-product-access-panel') || (tbody.closest('section') || tbody.closest('article'))); }
  }
  function hideNoisySignals(){
    document.querySelectorAll('li, .site-signal-card').forEach(el => {
      const body=text(el).toLowerCase();
      if(body.includes('no product-access match found for this site') || body.includes('source state: review')) hide(el);
    });
  }
  function removeDuplicateKpis(){
    document.querySelectorAll('.site-kpi').forEach(card => {
      const body=text(card).toLowerCase();
      if(body.includes('monitoring state') || body.includes('operational risk') || body.includes('last refresh')) hide(card);
    });
  }

  function hideReadinessStrip(){
    document.querySelectorAll('section, article, div').forEach(el => {
      const body=text(el).toLowerCase();
      if(body.includes('site workspace readiness') || body.includes('live source-backed status across runtime, alerts, discovery and data contracts') || body.includes('export planned')) hide(el);
    });
  }


  function hideBreadcrumb(){
    document.querySelectorAll('.jom-layout-breadcrumb').forEach(hide);
  }

  function run(){
    if(!isSiteWorkspace()) return;
    hideBreadcrumb();
    hideReadinessStrip();
    hideReportBars();
    hideEmptyProductAccess();
    hideNoisySignals();
    removeDuplicateKpis();
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', run); else run();
  [100,300,750,1500,3000,6000].forEach(t=>setTimeout(run,t));
})();

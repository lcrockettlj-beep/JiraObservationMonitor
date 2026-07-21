(function(){
  'use strict';
  function text(el){ return (el && el.textContent ? el.textContent : '').replace(/\s+/g,' ').trim(); }
  function hide(el){ if(el) el.classList.add('jom-site-empty-hidden-v1'); }
  function closestPanel(el){ return el && (el.closest('section') || el.closest('article') || el.closest('.jom-card') || el.closest('.site-card') || el.closest('.card') || el.closest('.panel')); }
  function isSiteWorkspace(){ return location.pathname.startsWith('/site/') || (document.body.getAttribute('data-jom-page') || '').includes('site'); }
  function hideReportsFooter(){
    document.querySelectorAll('section, article, div, footer').forEach(el => {
      const body=text(el).toLowerCase();
      if(!body) return;
      const compact=body.replace(/\s+/g,' ').trim();
      if(compact === 'reports html csv json' || compact.startsWith('reports html csv json') || (compact.startsWith('reports ') && compact.includes(' html') && compact.includes(' csv') && compact.includes(' json'))) {
        hide(el);
      }
    });
  }
  function hideEmptyProductAccess(){
    const body=document.getElementById('site-product-access-body');
    if(!body) return;
    const bodyText=text(body).toLowerCase();
    const empty = bodyText.includes('no source-backed product access currently available') || bodyText.includes('no product-access rows available') || bodyText.includes('has not yet produced product-access data') || bodyText.includes('registry only') || bodyText.includes('unavailable');
    if(empty){
      const panel=closestPanel(body);
      hide(panel);
    }
    // Also remove duplicate operational signal row.
    document.querySelectorAll('li, .site-signal-card, .site-signal-list li, div').forEach(el=>{
      const t=text(el).toLowerCase();
      if(t.includes('no product-access match found for this site') || t.includes('no source-backed product access currently available')) hide(el);
    });
  }
  function run(){
    if(!isSiteWorkspace()) return;
    hideEmptyProductAccess();
    hideReportsFooter();
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', run); else run();
  [250,750,1500,3000,5000].forEach(t=>setTimeout(run,t));
})();

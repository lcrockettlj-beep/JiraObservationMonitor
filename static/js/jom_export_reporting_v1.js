(function(){
  'use strict';
  const route = window.location.pathname;
  function reportTarget(){
    if(route.startsWith('/estate')) return 'estate';
    if(route.startsWith('/reference')) return 'admin';
    if(route.startsWith('/site/')) return 'site/' + encodeURIComponent(route.split('/').filter(Boolean).pop() || 'unknown');
    return 'executive';
  }
  function makeUrl(fmt){ return '/reports/generated/' + reportTarget() + '/' + fmt; }
  function addReportingActions(){
    if(document.querySelector('[data-jom-export-reporting="v1"]')) return;
    const host = document.querySelector('.jom-readiness-actions') || document.querySelector('.jom-actions') || document.querySelector('main') || document.body;
    const wrap = document.createElement('div');
    wrap.className = 'jom-export-reporting-actions';
    wrap.setAttribute('data-jom-export-reporting','v1');
    wrap.innerHTML = '<span class="jom-export-reporting-label">Reports</span>' +
      '<a class="jom-button jom-button--secondary" target="_blank" rel="noopener" href="'+makeUrl('html')+'">HTML</a>' +
      '<a class="jom-button jom-button--secondary" href="'+makeUrl('csv')+'">CSV</a>' +
      '<a class="jom-button jom-button--secondary" target="_blank" rel="noopener" href="'+makeUrl('json')+'">JSON</a>';
    host.appendChild(wrap);
  }
  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', addReportingActions);
  else addReportingActions();
})();

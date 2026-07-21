(function(){
  'use strict';
  const route = window.location.pathname || '/';

  // Command Centre is the live operational landing page.
  // Report export buttons belong in the left Reporting navigation and generated report pages,
  // not as a duplicated strip at the bottom of Command Centre.
  if (route === '/' || route === '') return;

  function reportTarget(){
    if(route.startsWith('/estate')) return 'estate';
    if(route.startsWith('/reference')) return 'admin';
    if(route.startsWith('/site/')) return 'site/' + encodeURIComponent(route.split('/').filter(Boolean).pop() || 'unknown');
    return 'executive';
  }

  function makeUrl(fmt){
    return '/reports/generated/' + reportTarget() + '/' + fmt;
  }

  function addReportingActions(){
    if(document.querySelector('[data-jom-export-reporting="v1"]')) return;
    const host = document.querySelector('.jom-readiness-actions') || document.querySelector('.jom-actions') || document.querySelector('main') || document.body;
    const wrap = document.createElement('div');
    wrap.className = 'jom-export-reporting-actions';
    wrap.setAttribute('data-jom-export-reporting','v1');
    wrap.innerHTML = '<strong class="jom-export-reporting-label">Reports</strong>' +
      '<a class="jom-button" href="' + makeUrl('html') + '">HTML</a>' +
      '<a class="jom-button" href="' + makeUrl('csv') + '">CSV</a>' +
      '<a class="jom-button" href="' + makeUrl('json') + '">JSON</a>';
    host.appendChild(wrap);
  }

  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', addReportingActions);
  else addReportingActions();
})();
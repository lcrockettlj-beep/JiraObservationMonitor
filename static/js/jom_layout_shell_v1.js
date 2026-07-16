/* JOM Frontend Consolidation Pack v1
   Adds page purpose, breadcrumb, active navigation, and shared operator actions.
*/
(function(){
  const pageConfig = {
    '/': {
      name: 'Command Centre',
      purpose: 'Live operational command surface for estate health, alerts, discovery and runtime posture.',
      actions: ['Refresh live view', 'Review alerts', 'Open Estate']
    },
    '/estate': {
      name: 'Estate',
      purpose: 'Operational workspace for site registry, discovery, product access and estate investigation.',
      actions: ['Filter sites', 'Review discovery', 'Open Admin']
    },
    '/reference': {
      name: 'Admin',
      purpose: 'Governance workspace for admin truth, user footprint, discovery control and platform status.',
      actions: ['Review discovery queue', 'Check user footprint', 'Inspect admin truth']
    }
  };
  function currentPath(){
    const path = window.location.pathname || '/';
    return pageConfig[path] ? path : '/';
  }
  function getMain(){
    return document.querySelector('main') || document.querySelector('.jom-main') || document.querySelector('.content') || document.body;
  }
  function addBreadcrumb(config){
    if(document.querySelector('.jom-layout-breadcrumb')) return;
    const main = getMain();
    const crumb = document.createElement('div');
    crumb.className = 'jom-layout-breadcrumb';
    crumb.innerHTML = '<span>JOM</span><span>/</span><strong>' + config.name + '</strong>';
    const purpose = document.createElement('div');
    purpose.className = 'jom-layout-page-purpose';
    purpose.textContent = config.purpose;
    const first = main.firstElementChild;
    if(first){
      main.insertBefore(purpose, first);
      main.insertBefore(crumb, purpose);
    } else {
      main.appendChild(crumb);
      main.appendChild(purpose);
    }
  }
  function addActions(config){
    if(document.querySelector('.jom-layout-action-row')) return;
    const main = getMain();
    const row = document.createElement('div');
    row.className = 'jom-layout-action-row';
    config.actions.forEach(function(label){
      const pill = document.createElement('span');
      pill.className = 'jom-layout-action-pill';
      pill.textContent = label;
      row.appendChild(pill);
    });
    const purpose = document.querySelector('.jom-layout-page-purpose');
    if(purpose && purpose.parentNode){
      purpose.parentNode.insertBefore(row, purpose.nextSibling);
    } else if(main.firstChild){
      main.insertBefore(row, main.firstChild);
    } else {
      main.appendChild(row);
    }
  }
  function markActiveNav(config){
    const path = window.location.pathname || '/';
    const links = document.querySelectorAll('a[href]');
    links.forEach(function(link){
      try {
        const href = link.getAttribute('href');
        if(!href) return;
        const isActive = href === path || (path === '/' && href === '/') || (path === '/reference' && href.indexOf('/reference') === 0);
        if(isActive){
          link.classList.add('active');
          link.setAttribute('aria-current', 'page');
        }
      } catch(e) {}
    });
    document.title = 'JOM - ' + config.name;
  }
  function init(){
    const cfg = pageConfig[currentPath()];
    addBreadcrumb(cfg);
    addActions(cfg);
    markActiveNav(cfg);
  }
  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();


// JOM Operational Readiness Expansion v1
(function(){
  const pageLabels = {
    '/': 'Command Centre',
    '/estate': 'Estate Operations Hub',
    '/reference': 'Admin Intelligence Centre'
  };
  function q(sel){ return document.querySelector(sel); }
  async function getJson(url){
    const res = await fetch(url, {cache:'no-store'});
    if(!res.ok) throw new Error(url + ' returned ' + res.status);
    return await res.json();
  }
  function mode(value){
    const v = String(value || '').toLowerCase();
    if(v.includes('ok') || v.includes('idle') || v.includes('healthy') || v.includes('available')) return 'ok';
    if(v.includes('error') || v.includes('fail') || v.includes('critical')) return 'risk';
    if(v.includes('review') || v.includes('discovered') || v.includes('warning')) return 'review';
    return 'info';
  }
  function pill(label, value, state){
    const css = 'jom-readiness-pill jom-readiness-pill--' + (state || mode(value));
    return `<span class="${css}"><span>${label}</span><strong>${value}</strong></span>`;
  }
  function routeLabel(){
    const path = window.location.pathname;
    if(path.startsWith('/site/')) return 'Site Workspace';
    return pageLabels[path] || 'JOM Workspace';
  }
  function injectStrip(){
    if(document.querySelector('[data-jom-readiness-strip="v1"]')) return document.querySelector('[data-jom-readiness-strip="v1"]');
    const main = q('main') || q('.jom-shell') || document.body;
    const strip = document.createElement('section');
    strip.className = 'jom-readiness-strip';
    strip.setAttribute('data-jom-readiness-strip', 'v1');
    strip.innerHTML = `
      <div class="jom-readiness-title">
        <strong>${routeLabel()} readiness</strong>
        <span>Live source-backed status across runtime, alerts, discovery and data contracts.</span>
      </div>
      <div class="jom-readiness-pills" id="jom-readiness-pills"><span class="jom-readiness-pill jom-readiness-pill--info">Loading...</span></div>`;
    main.insertBefore(strip, main.firstChild);
    return strip;
  }
  function addActionRows(){
    const pages = [document.querySelector('main'), document.querySelector('.jom-shell')].filter(Boolean);
    const root = pages[0];
    if(!root || root.dataset.jomReadinessActions === 'true') return;
    root.dataset.jomReadinessActions = 'true';
    const row = document.createElement('div');
    row.className = 'jom-action-row';
    row.innerHTML = `
      <a class="jom-action-button" href="/">Command Centre</a>
      <a class="jom-action-button" href="/estate">Estate</a>
      <a class="jom-action-button" href="/reference">Admin</a>
      <button class="jom-export-placeholder" type="button" aria-disabled="true" title="Planned export placeholder">Export planned</button>`;
    const strip = document.querySelector('[data-jom-readiness-strip="v1"]');
    if(strip) strip.appendChild(row);
  }
  async function render(){
    const strip = injectStrip();
    try{
      const [summary, alerts, registry, sourceState] = await Promise.all([
        getJson('/operator/summary'),
        getJson('/operator/alerts'),
        getJson('/registry/sites'),
        getJson('/api/source-state')
      ]);
      const runtime = summary && summary.runtime ? summary.runtime : {};
      const reg = registry && registry.summary ? registry.summary : {};
      const alertCount = alerts && alerts.count != null ? alerts.count : 0;
      const runtimeValue = runtime.last_result_status || runtime.state || 'available';
      const discovered = reg.discovered_count != null ? reg.discovered_count : '0';
      const monitored = reg.monitored_count != null ? reg.monitored_count : '0';
      const sourceValue = sourceState && sourceState.schema ? 'available' : 'review';
      const html = [
        pill('Runtime', runtimeValue, mode(runtimeValue)),
        pill('Alerts', alertCount, alertCount ? 'review' : 'ok'),
        pill('Monitored', monitored, 'ok'),
        pill('Discovered', discovered, Number(discovered) ? 'review' : 'ok'),
        pill('Sources', sourceValue, mode(sourceValue))
      ].join('');
      const target = document.getElementById('jom-readiness-pills');
      if(target) target.innerHTML = html;
      document.body.dataset.jomReadiness = 'ready';
      addActionRows();
    }catch(error){
      const target = document.getElementById('jom-readiness-pills');
      if(target) target.innerHTML = pill('Readiness', 'review', 'review');
      console.warn('JOM readiness strip failed', error);
      addActionRows();
    }
  }
  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', render);
  else render();
})();

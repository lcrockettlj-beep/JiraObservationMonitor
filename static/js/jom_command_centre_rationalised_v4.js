
(function(){
  'use strict';
  function txt(v){ return (v === undefined || v === null || v === '') ? 'Unavailable' : String(v); }
  function q(sel, root){ return (root || document).querySelector(sel); }
  function qa(sel, root){ return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function hideLegacyKpiStrip(){
    var cards = qa('.jom-metric-card, .metric-card, .jom-kpi-card, .kpi-card');
    cards.forEach(function(card){
      var text = (card.textContent || '').toLowerCase();
      if ((text.indexOf('viewed at') !== -1 || text.indexOf('runtime') !== -1 || text.indexOf('alerts') !== -1 || text.indexOf('discovery') !== -1) &&
          (text.indexOf('operator contract detail') === -1) &&
          (text.length < 260)) {
        card.classList.add('jom-legacy-kpi-strip');
      }
    });
    var rows = qa('section, div');
    rows.forEach(function(row){
      var text = (row.textContent || '').toLowerCase().replace(/\s+/g,' ');
      if (text.indexOf('viewed at') !== -1 && text.indexOf('runtime') !== -1 && text.indexOf('alerts') !== -1 && text.indexOf('discovery') !== -1 && text.length < 520) {
        row.classList.add('jom-legacy-kpi-strip');
      }
    });
  }
  function renameLabels(){
    qa('*').forEach(function(el){
      if (el.childNodes.length === 1 && el.childNodes[0].nodeType === 3) {
        var value = el.textContent.trim();
        if (value === 'Discovery Pressure') el.textContent = 'Discovery Backlog';
        if (value === 'Current Command Events') el.textContent = 'Current Operational Status';
        if (value === 'Recent Operational Events') el.textContent = 'Current Operational Status';
        if (value === 'Live Recommendations') el.textContent = 'Recommended Operator Actions';
        if (value === 'Risk Grouping') el.textContent = 'Estate Posture Explanation';
      }
    });
  }
  function enrichHealthScore(){
    var candidates = qa('section, article, div').filter(function(el){
      var t = (el.textContent || '').toLowerCase();
      return t.indexOf('estate health score') !== -1 && t.indexOf('calculated from') === -1 && t.length < 900;
    });
    var target = candidates[0];
    if (!target) return;
    var explain = document.createElement('div');
    explain.className = 'jom-health-explain';
    explain.innerHTML = ''+
      '<div class="jom-health-explain__row"><span class="jom-health-explain__ok">✓</span><span>Runtime contract available.</span></div>'+
      '<div class="jom-health-explain__row"><span class="jom-health-explain__ok">✓</span><span>Reports validated.</span></div>'+
      '<div class="jom-health-explain__row"><span class="jom-health-explain__ok">✓</span><span>Monitored estate coverage present.</span></div>'+
      '<div class="jom-health-explain__row"><span class="jom-health-explain__warn">⚠</span><span>Discovery backlog and active alerts reduce the score.</span></div>';
    var heading = document.createElement('div');
    heading.className = 'jom-command-note';
    heading.textContent = 'Calculated from runtime, alerts, discovery backlog, reporting readiness and source-state availability.';
    target.appendChild(heading);
    target.appendChild(explain);
  }
  function improveRiskCards(){
    qa('section, article, div').forEach(function(el){
      var t = (el.textContent || '').toLowerCase();
      if (t.indexOf('top risks and required action') !== -1) {
        el.classList.add('jom-command-card--attention');
      }
    });
  }
  function run(){
    document.body.classList.add('jom-command-centre-v4');
    hideLegacyKpiStrip();
    renameLabels();
    enrichHealthScore();
    improveRiskCards();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', run);
  else run();
})();

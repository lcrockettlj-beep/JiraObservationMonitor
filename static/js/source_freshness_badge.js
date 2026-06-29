(function () {
  function stateClass(state) {
    if (state === 'CURRENT') return 'source-freshness-badge--current';
    if (state === 'AGING') return 'source-freshness-badge--aging';
    if (state === 'STALE') return 'source-freshness-badge--stale';
    if (state === 'MISSING') return 'source-freshness-badge--missing';
    return 'source-freshness-badge--unknown';
  }
  function pageName() {
    if (location.pathname === '/' || location.pathname === '') return 'Home';
    if (location.pathname.indexOf('/estate') === 0) return 'Estate';
    if (location.pathname.indexOf('/reference') === 0 || location.pathname.indexOf('/admin') === 0) return 'Admin';
    if (location.pathname.indexOf('/site') === 0) return 'Site';
    return 'Other';
  }
  function fmtAge(hours) {
    if (hours === null || hours === undefined) return 'age unknown';
    if (hours < 1) return Math.max(1, Math.round(hours * 60)) + 'm old';
    return Number(hours).toFixed(1) + 'h old';
  }
  function label(source) { return source.operator_label || source.freshness_state || 'REVIEW'; }
  function render(payload) {
    var existing = document.getElementById('source-freshness-badge');
    if (existing) existing.remove();
    var page=pageName();
    var sources=Array.isArray(payload.sources)?payload.sources.filter(function(source){return Array.isArray(source.pages)&&source.pages.indexOf(page)!==-1;}):[];
    var summary=payload.summary||{}; var state=summary.overall_state||'UNKNOWN';
    var generated=payload.display_generated_at_utc||payload.generated_at_utc||'timestamp unavailable';
    var root=document.createElement('section'); root.id='source-freshness-badge'; root.className='source-freshness-badge signal-border';
    root.innerHTML='<div class="source-freshness-badge__head"><div><strong>Source Freshness</strong><span>Generated: '+generated+'</span></div><span class="source-freshness-badge__state '+stateClass(state)+'">'+state+'</span></div><div class="source-freshness-badge__grid"></div>';
    var grid=root.querySelector('.source-freshness-badge__grid');
    if(!sources.length){grid.innerHTML='<div class="source-freshness-row source-freshness-row--unknown"><span>No freshness sources mapped for this page.<small>REVIEW REQUIRED</small></span><b>REVIEW</b></div>';}
    else sources.forEach(function(source){
      var row=document.createElement('div'); var stateName=source.freshness_state||'UNKNOWN';
      row.className='source-freshness-row source-freshness-row--'+String(stateName).toLowerCase();
      var type=source.source_type||'SOURCE'; var age=fmtAge(source.age_hours); var time=source.display_timestamp_utc||'no timestamp';
      row.innerHTML='<span>'+source.label+'<small>'+type+' · '+age+' · '+time+'</small></span><b>'+label(source)+'</b>';
      grid.appendChild(row);
    });
    var target=document.querySelector('.page');
    if(target){var nav=target.querySelector('.top-nav'); if(nav&&nav.nextSibling) target.insertBefore(root,nav.nextSibling); else target.insertBefore(root,target.firstChild);} else document.body.insertBefore(root,document.body.firstChild);
  }
  function init(){fetch('/static/data/source_freshness_audit.json',{cache:'no-store'}).then(function(r){if(!r.ok)throw new Error('missing');return r.json();}).then(render).catch(function(){render({display_generated_at_utc:'DATA UNAVAILABLE',summary:{overall_state:'MISSING'},sources:[]});});}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init); else init();
})();

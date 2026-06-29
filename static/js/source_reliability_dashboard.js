(function () {
  function cls(status) {
    if (status === 'ok') return 'source-reliability--ok';
    if (status === 'review') return 'source-reliability--review';
    return 'source-reliability--attention';
  }
  function pageAllowed() {
    return location.pathname === '/' || location.pathname.indexOf('/estate') === 0 || location.pathname.indexOf('/reference') === 0 || location.pathname.indexOf('/admin') === 0;
  }
  function render(payload) {
    if (!pageAllowed()) return;
    var existing = document.getElementById('source-reliability-dashboard');
    if (existing) existing.remove();
    var root = document.createElement('section');
    root.id = 'source-reliability-dashboard';
    root.className = 'source-reliability-dashboard signal-border ' + cls(payload.overall_status);
    var issues = Array.isArray(payload.issues) ? payload.issues : [];
    root.innerHTML = '<div class="source-reliability-dashboard__head"><div><strong>Source Reliability</strong><span>Generated: ' + (payload.generated_at_utc || 'unknown') + '</span></div><b>' + (payload.overall_status || 'unknown').toUpperCase() + '</b></div><div class="source-reliability-dashboard__body"></div>';
    var body = root.querySelector('.source-reliability-dashboard__body');
    if (!issues.length) {
      body.innerHTML = '<div class="source-reliability-issue source-reliability-issue--ok"><span>No source reliability issues detected.</span><b>OK</b></div>';
    } else {
      issues.slice(0, 8).forEach(function (issue) {
        var row = document.createElement('div');
        row.className = 'source-reliability-issue';
        row.innerHTML = '<span>' + (issue.source || 'Source') + '<small>' + (issue.reason || issue.path || '') + '</small></span><b>' + (issue.state || 'REVIEW') + '</b>';
        body.appendChild(row);
      });
    }
    var target = document.querySelector('.page');
    if (!target) return;
    var freshness = document.getElementById('source-freshness-badge');
    if (freshness && freshness.nextSibling) target.insertBefore(root, freshness.nextSibling);
    else if (freshness) target.appendChild(root);
    else target.insertBefore(root, target.firstChild);
  }
  function init() {
    fetch('/static/data/source_reliability_status.json', {cache:'no-store'}).then(function (r) {
      if (!r.ok) throw new Error('missing'); return r.json();
    }).then(render).catch(function () {});
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();

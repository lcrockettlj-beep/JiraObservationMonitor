
(() => {
  function statusWeight(value) {
    if (value === 'critical') return 300;
    if (value === 'warning') return 200;
    return 100;
  }

  function riskWeight(value) {
    if (value === 'high') return 30;
    if (value === 'medium') return 20;
    return 10;
  }

  function changeWeight(value) {
    if (value === 'critical') return 30;
    if (value === 'warning') return 20;
    return 0;
  }

  function applyThemeHighlight(row) {
    var score = Number(row.dataset.priority || '0');
    if (score >= 330) row.classList.add('priority-row--alert');
    else if (score >= 220) row.classList.add('priority-row--focus');
  }

  function sortBoard() {
    var body = document.querySelector('.priority-body');
    if (!body) return;
    var rows = Array.from(body.querySelectorAll('.priority-row'));
    rows.forEach(function (row) {
      var score = statusWeight(row.dataset.status) + riskWeight(row.dataset.riskBand) + changeWeight(row.dataset.changeLevel);
      row.dataset.priority = String(score);
      applyThemeHighlight(row);
    });
    rows.sort(function (a, b) {
      return Number(b.dataset.priority || '0') - Number(a.dataset.priority || '0');
    });
    rows.forEach(function (row) { body.appendChild(row); });
  }

  function highlightTopAction() {
    var first = document.querySelector('.priority-body .priority-row');
    if (!first) return;
    var btn = first.querySelector('.pill');
    if (btn) btn.classList.add('pill--primary-action');
  }

  function start() {
    sortBoard();
    highlightTopAction();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, { once: true });
  else start();
})();

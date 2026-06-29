(function () {
  function setUnavailable(el) {
    if (!el) return;
    el.textContent = 'DATA UNAVAILABLE';
    el.classList.add('truth-unavailable');
  }

  function safeNumber(value) {
    if (value === null || value === undefined || value === '') {
      return null;
    }
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }

  function safeText(value) {
    if (value === null || value === undefined || value === '') {
      return null;
    }
    return String(value);
  }

  function applyValue(id, value, formatter) {
    const el = document.getElementById(id);
    if (!el) return;

    if (value === null) {
      setUnavailable(el);
      return;
    }

    el.textContent = formatter ? formatter(value) : value;
  }

  function applyRatio(id, a, b) {
    const el = document.getElementById(id);
    if (!el) return;

    if (!a || !b || a === 0) {
      setUnavailable(el);
      return;
    }

    el.textContent = (b / a).toFixed(2);
  }

  window.TruthGuard = {
    safeNumber,
    safeText,
    applyValue,
    applyRatio
  };
})();
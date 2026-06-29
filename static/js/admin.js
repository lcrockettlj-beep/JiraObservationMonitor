(function () {
  function setText(id, value) {
    var el = document.getElementById(id);
    if (!el) return;
    el.innerText = value;
  }
  function number(value) {
    var parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  Promise.all([
    fetch('/static/data/admin_truth_v2.json', { cache: 'no-store' }).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; }),
    fetch('/static/data/user_footprint.json', { cache: 'no-store' }).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; })
  ]).then(function (results) {
    var adminTruth = results[0] || {};
    var footprint = results[1] || {};
    var summary = adminTruth.summary || {};
    var footprintSummary = footprint.summary || {};
    var humans = number(summary.admin_human_users);
    var seats = number(summary.billing_jira_seats);
    var namedUsers = number(footprintSummary.users_analyzed || footprintSummary.named_unique_users);
    var assignments = number(footprintSummary.total_product_access_assignments);
    setText('identity', humans === null ? 'Humans: DATA UNAVAILABLE' : 'Humans: ' + humans.toLocaleString());
    setText('billing', seats === null ? 'Jira Seats: DATA UNAVAILABLE' : 'Jira Seats: ' + seats.toLocaleString());
    if (humans && seats) {
      setText('insight', 'Seat/User Ratio: ' + (seats / humans).toFixed(2) + ' | Named Users: ' + (namedUsers === null ? 'DATA UNAVAILABLE' : namedUsers.toLocaleString()) + ' | Assignments: ' + (assignments === null ? 'DATA UNAVAILABLE' : assignments.toLocaleString()));
    } else {
      setText('insight', 'Seat/User Ratio: DATA UNAVAILABLE');
    }
  });
})();

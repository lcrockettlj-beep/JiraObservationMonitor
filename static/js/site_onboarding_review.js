document.addEventListener("DOMContentLoaded", () => {
 fetch("/static/data/site_onboarding_review.json")
  .then(r => r.json())
  .then(data => {
    const host = document.getElementById("site-onboarding-panel") || document.body;
    const div = document.createElement("div");
    div.innerHTML = `<h3>Site Onboarding Queue (${data.count})</h3>`;
    data.queue.forEach(s => {
      const row = document.createElement("div");
      row.innerHTML = `${s.site_key} - ${s.classification}`;
      div.appendChild(row);
    });
    host.appendChild(div);
  });
});

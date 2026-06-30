document.addEventListener("DOMContentLoaded", () => {
  const url = "/static/data/site_onboarding_review.json";
  function panelHtml(title, rows) {
    if (!rows || rows.length === 0) return `<section class="site-onboarding-block"><h3>${title}</h3><p>No sites.</p></section>`;
    const body = rows.map(s => `
      <tr>
        <td>${s.site_key || ""}</td>
        <td>${s.classification || ""}</td>
        <td>${s.decision || "pending"}</td>
        <td><code>${s.approve_command || ""}</code></td>
        <td><code>${s.ignore_command || ""}</code></td>
      </tr>`).join("");
    return `<section class="site-onboarding-block"><h3>${title}</h3><table class="site-onboarding-table"><thead><tr><th>Site</th><th>Classification</th><th>Decision</th><th>Approve command</th><th>Ignore command</th></tr></thead><tbody>${body}</tbody></table></section>`;
  }
  fetch(url, { cache: "no-store" }).then(r => r.json()).then(data => {
    let host = document.getElementById("site-onboarding-panel");
    if (!host) {
      const op = document.getElementById("operational-console-panel") || document.body;
      host = document.createElement("section");
      host.id = "site-onboarding-panel";
      host.className = "site-onboarding";
      op.appendChild(host);
    }
    host.innerHTML = `
      <div class="site-onboarding-header"><h2>Site Onboarding Review</h2><span>${data.summary?.pending_count || 0} pending</span></div>
      <p class="site-onboarding-note">${data.safety_note || ""}</p>
      ${panelHtml("Pending", data.pending)}
      ${panelHtml("Approved decisions", data.approved)}
      ${panelHtml("Ignored decisions", data.ignored)}
    `;
  }).catch(err => console.warn("Site onboarding review failed", err));
});

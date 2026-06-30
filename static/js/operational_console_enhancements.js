(() => {
  const insightUrl = "/static/data/operational_console_insights.json";
  const rolesUrl = "/static/data/operational_console_role_views.json";

  function makeEl(tag, className, text) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined) el.textContent = text;
    return el;
  }

  function renderTable(rows, limit = 50) {
    if (!Array.isArray(rows) || rows.length === 0) return "<p class='jom-enh-empty'>No rows available.</p>";
    const keys = Array.from(new Set(rows.flatMap(row => Object.keys(row)))).slice(0, 8);
    const head = keys.map(k => `<th>${k}</th>`).join("");
    const body = rows.slice(0, limit).map(row => `<tr>${keys.map(k => `<td>${Array.isArray(row[k]) ? row[k].join(", ") : (row[k] ?? "")}</td>`).join("")}</tr>`).join("");
    return `<table class="jom-enh-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
  }

  function downloadLink(href, label) {
    return `<a class="jom-enh-export" href="${href}" download>${label}</a>`;
  }

  async function init() {
    const panel = document.getElementById("operational-console-panel");
    if (!panel) return;
    const [insights, roles] = await Promise.all([
      fetch(insightUrl, { cache: "no-store" }).then(r => r.json()).catch(() => null),
      fetch(rolesUrl, { cache: "no-store" }).then(r => r.json()).catch(() => null),
    ]);
    if (!insights) return;

    let enh = document.getElementById("jom-opcon-enhancements");
    if (!enh) {
      enh = document.createElement("section");
      enh.id = "jom-opcon-enhancements";
      enh.className = "jom-opcon-enhancements";
      panel.appendChild(enh);
    }

    const roleOptions = roles?.roles ? Object.keys(roles.roles).map(role => `<option value="${role}">${roles.roles[role].label}</option>`).join("") : "";
    enh.innerHTML = `
      <div class="jom-enh-toolbar">
        <div><strong>Operational Insights</strong><small>Risk score: ${insights.summary?.operator_risk_score ?? 0} (${insights.summary?.operator_risk_band ?? "unknown"})</small></div>
        <label>Site filter <select id="jom-enh-site-filter"><option value="all">All</option><option value="monitored">Monitored</option><option value="discovered">Discovered</option></select></label>
        <label>Role view <select id="jom-enh-role-view">${roleOptions}</select></label>
      </div>
      <div class="jom-enh-exports">
        ${downloadLink(insights.exports?.sites_csv, "Export sites CSV")}
        ${downloadLink(insights.exports?.advisories_csv, "Export advisories CSV")}
        ${downloadLink(insights.exports?.users_sample_csv, "Export users CSV")}
      </div>
      <div id="jom-enh-table-host"></div>
    `;

    const host = document.getElementById("jom-enh-table-host");
    const filter = document.getElementById("jom-enh-site-filter");
    function refreshTable() {
      const value = filter.value;
      let rows = insights.tables?.sites || [];
      if (value !== "all") rows = rows.filter(row => row.classification === value || (value === "monitored" && row.is_monitored === true));
      host.innerHTML = `<h3>Site Coverage</h3>${renderTable(rows, 100)}<h3>Advisories</h3>${renderTable(insights.tables?.advisories || [], 20)}`;
    }
    filter.addEventListener("change", refreshTable);
    refreshTable();
  }

  document.addEventListener("DOMContentLoaded", init);
})();

(() => {
  const statusUrl = "/static/data/operational_console_ui_view.json";
  const drillUrl = "/static/data/operational_console_drilldowns.json";
  const label = (value) => value === true ? "OK" : value === false ? "Attention" : value == null ? "Unknown" : String(value).replaceAll("_", " ");
  function setPill(el, status) { el.textContent = label(status); el.dataset.status = String(status || "unknown").toLowerCase(); }
  function card(name, title, status, detailKey) {
    const button = document.createElement("button");
    button.className = "jom-opcon-card";
    button.type = "button";
    button.dataset.detailKey = detailKey;
    button.innerHTML = `<span class="jom-opcon-card-title">${title}</span><strong>${label(status)}</strong><small>${name}</small>`;
    return button;
  }
  function renderDrilldown(container, drilldowns, key) {
    const panel = drilldowns?.panels?.[key];
    if (!panel) return;
    container.hidden = false;
    container.innerHTML = `<h3>${panel.title || key}</h3><pre>${JSON.stringify(panel, null, 2)}</pre>`;
  }
  async function init() {
    const panel = document.getElementById("operational-console-panel");
    if (!panel) return;
    const overall = document.getElementById("jom-opcon-overall");
    const cards = document.getElementById("jom-opcon-cards");
    const drill = document.getElementById("jom-opcon-drilldown");
    try {
      const [view, drilldowns] = await Promise.all([
        fetch(statusUrl, { cache: "no-store" }).then(r => r.json()),
        fetch(drillUrl, { cache: "no-store" }).then(r => r.json()).catch(() => null),
      ]);
      setPill(overall, view.overall_status);
      cards.innerHTML = "";
      cards.appendChild(card("Scheduler", "Scheduler Health", view.badges?.scheduler_ok, "scheduler"));
      cards.appendChild(card("Reliability", "Source Reliability", view.badges?.reliability_ok, "source_reliability"));
      cards.appendChild(card("Runtime", "Runtime Advisory", `${view.badges?.advisory_count || 0} advisory`, "runtime_refresh"));
      cards.appendChild(card("Sites", "Site Coverage", `${view.badges?.monitored_site_count || 0} monitored`, "site_registry"));
      cards.addEventListener("click", (event) => {
        const button = event.target.closest("button[data-detail-key]");
        if (button) renderDrilldown(drill, drilldowns, button.dataset.detailKey);
      });
    } catch (error) {
      setPill(overall, "attention");
      cards.innerHTML = `<div class="jom-opcon-error">Operational console failed to load: ${error}</div>`;
    }
  }
  document.addEventListener("DOMContentLoaded", init);
})();

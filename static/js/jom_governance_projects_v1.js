(() => {
  "use strict";
  const endpoint = "/api/governance/projects";
  const $ = (id) => document.getElementById(id);
  const fields = ["search", "site", "type", "style", "privacy", "simplified", "category"];
  let projects = [];
  const text = (value) => value === null || value === undefined || value === "" ? "Unavailable" : String(value);
  const option = (value) => { const el=document.createElement("option"); el.value=value; el.textContent=value; return el; };
  const fill = (id, values) => [...new Set(values.filter(Boolean))].sort().forEach(v => $(id).appendChild(option(v)));
  const privacy = (v) => v === true ? "private" : v === false ? "open" : "unavailable";
  const simplified = (v) => v === true ? "simplified" : v === false ? "standard" : "unavailable";
  const cell = (value) => { const td=document.createElement("td"); td.textContent=text(value); return td; };
  function render() {
    const q=$("gp-search").value.trim().toLowerCase();
    const selected={}; fields.slice(1).forEach(f => selected[f]=$("gp-"+f).value);
    const rows=projects.filter(p => {
      const category=p.project_category && p.project_category.name || "";
      return (!q || `${p.project_name||""} ${p.project_key||""}`.toLowerCase().includes(q)) &&
        (!selected.site || p.site_key===selected.site) && (!selected.type || p.project_type_key===selected.type) &&
        (!selected.style || p.style===selected.style) && (!selected.privacy || privacy(p.is_private)===selected.privacy) &&
        (!selected.simplified || simplified(p.simplified)===selected.simplified) && (!selected.category || category===selected.category);
    });
    const body=$("gp-rows"); body.replaceChildren();
    rows.forEach(p => { const tr=document.createElement("tr"); const category=p.project_category && p.project_category.name;
      [p.project_name,p.project_key,p.site_name||p.site_key,p.project_type_key,p.style,privacy(p.is_private),simplified(p.simplified),category].forEach(v=>tr.appendChild(cell(v))); body.appendChild(tr); });
    $("gp-filter-count").textContent=`${rows.length} shown`; $("gp-empty").hidden=rows.length!==0;
  }
  function renderCapabilities(capabilities) {
    const host=$("gp-capabilities"); host.replaceChildren();
    Object.entries(capabilities||{}).forEach(([key,value]) => { const article=document.createElement("article"); const h=document.createElement("h3"); const p=document.createElement("p"); h.textContent=key.split("_").map(x=>x[0].toUpperCase()+x.slice(1)).join(" "); p.textContent=value.reason||"Unavailable from current authority."; article.append(h,p); host.appendChild(article); });
  }
  async function load() {
    try { const response=await fetch(endpoint,{headers:{Accept:"application/json"}}); const data=await response.json();
      renderCapabilities(data.capabilities); if(!response.ok || data.available!==true) throw new Error(data.reason||"Project Inventory authority unavailable.");
      projects=Array.isArray(data.projects)?data.projects:[]; $("gp-count").textContent=text(data.summary&&data.summary.visible_project_count); $("gp-status").textContent=`Authority validated. ${projects.length} visible projects loaded read-only.`; $("gp-status").classList.add("gp__status--ok");
      fill("gp-site",projects.map(p=>p.site_key)); fill("gp-type",projects.map(p=>p.project_type_key)); fill("gp-style",projects.map(p=>p.style)); fill("gp-category",projects.map(p=>p.project_category&&p.project_category.name)); render();
    } catch(error) { projects=[]; $("gp-status").textContent=error.message; $("gp-status").classList.add("gp__status--blocked"); $("gp-count").textContent="Unavailable"; render(); }
  }
  fields.forEach(f => $("gp-"+f).addEventListener(f==="search"?"input":"change",render)); load();
})();

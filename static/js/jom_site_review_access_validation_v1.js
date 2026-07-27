(function(){
  'use strict';
  const siteKey = document.body.getAttribute('data-site-key') || '';
  const $ = id => document.getElementById(id);
  const set = (id, value) => { const el=$(id); if(el) el.textContent=String(value || ''); };
  async function getJson(url){ const r=await fetch(url,{cache:'no-store'}); const j=await r.json(); if(!r.ok) throw new Error(j.error||j.message||url+' failed'); return j; }
  async function postJson(url,payload){ const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload||{})}); const j=await r.json(); if(!r.ok) throw new Error(j.error||j.message||url+' failed'); return j; }
  function statusBox(){ return $('site-review-validation-status'); }
  function setStatus(text,state){ const el=statusBox(); if(!el) return; el.textContent=text; if(state) el.setAttribute('data-state',state); }
  function enableButton(){ return document.querySelector('[data-enable-monitoring]'); }
  function validateButton(){ return document.querySelector('[data-validate-access]'); }
  function applyGate(validation){
    const btn=enableButton(); if(!btn) return;
    const ok=validation && validation.access_valid===true;
    const monitored=/monitoring enabled/i.test(btn.textContent || '');
    if(!monitored && btn.style.display !== 'none'){ btn.disabled=!ok; }
    if(ok){ setStatus('Access validated. Monitoring can be enabled in JOM.', 'ok'); }
    else if(validation && validation.status){ setStatus('Access validation required before monitoring can be enabled. Current status: '+validation.status+'. '+(validation.reason||''), validation.status==='ok'?'ok':'blocked'); }
    else { setStatus('Credential access has not been validated yet. Click Validate Access before enabling monitoring.', 'blocked'); }
  }
  async function refreshValidation(){
    try{ const payload=await getJson(`/api/site-review/${encodeURIComponent(siteKey)}/access-validation`); applyGate(payload.validation || {}); }
    catch(error){ setStatus('Credential validation status unavailable: '+error.message, 'failed'); const btn=enableButton(); if(btn) btn.disabled=true; }
  }
  function wire(){
    const vbtn=validateButton();
    if(vbtn && !vbtn.dataset.validationWired){
      vbtn.dataset.validationWired='true';
      vbtn.addEventListener('click', async()=>{
        try{
          vbtn.disabled=true; setStatus('Validating Atlassian access using backend credentials...', 'pending');
          const result=await postJson(`/api/site-review/${encodeURIComponent(siteKey)}/validate-access`, {actor:'operator'});
          applyGate(result.validation || {});
        }catch(error){ setStatus('Access validation failed: '+error.message, 'failed'); const btn=enableButton(); if(btn) btn.disabled=true; }
        finally{ vbtn.disabled=false; }
      });
    }
    refreshValidation();
    setTimeout(refreshValidation, 800);
    setTimeout(refreshValidation, 2000);
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', wire); else wire();
})();

// === Estate Validate Access OAuth Action Exact Handler Repair v1 START ===
(function () {
  "use strict";

  if (window.__jomEstateValidateAccessOauthExactHandlerWired) return;
  window.__jomEstateValidateAccessOauthExactHandlerWired = true;

  function isOauthActionPayload(payload) {
    return !!(payload && payload.action === "open_authorization_url" && payload.authorization_url);
  }

  function findActionContainer() {
    return document.querySelector(".site-review-actions") ||
      document.querySelector(".site-review-rail") ||
      document.querySelector("aside") ||
      document.querySelector("[data-site-review-root]") ||
      document.querySelector("main") ||
      document.body;
  }

  function findErrorAnchor() {
    var nodes = Array.prototype.slice.call(document.querySelectorAll("body *"));
    return nodes.find(function (node) {
      if (!node || !node.textContent) return false;
      return node.textContent.indexOf("oauth_authorisation_required") !== -1 ||
        node.textContent.indexOf("oauth_authorization_required") !== -1;
    }) || null;
  }

  function showOauthAction(payload) {
    if (!isOauthActionPayload(payload)) return;
    window.__jomLatestValidateAccessOauthPayload = payload;

    var existing = document.getElementById("jom-estate-validate-access-oauth-action-v1");
    if (existing) existing.remove();

    var box = document.createElement("section");
    box.id = "jom-estate-validate-access-oauth-action-v1";
    box.setAttribute("role", "status");
    box.style.border = "1px solid rgba(37, 99, 235, 0.45)";
    box.style.background = "rgba(37, 99, 235, 0.08)";
    box.style.borderRadius = "14px";
    box.style.padding = "14px";
    box.style.margin = "12px 0";
    box.style.display = "grid";
    box.style.gap = "10px";

    var title = document.createElement("strong");
    title.textContent = "Atlassian authorisation required";

    var message = document.createElement("p");
    message.style.margin = "0";
    message.textContent = payload.message || "Authorise Atlassian access before validating this site for monitoring.";

    var button = document.createElement("button");
    button.type = "button";
    button.textContent = "Authorise Atlassian Access";
    button.className = "estate-site-link estate-site-link--button";
    button.addEventListener("click", function () {
      window.open(payload.authorization_url, "_blank", "noopener,noreferrer");
    });

    box.appendChild(title);
    box.appendChild(message);
    box.appendChild(button);

    var anchor = findErrorAnchor();
    if (anchor && anchor.parentNode) {
      anchor.parentNode.insertBefore(box, anchor.nextSibling);
      return;
    }

    var container = findActionContainer();
    container.appendChild(box);
  }

  window.jomEstateShowValidateAccessOauthAction = showOauthAction;

  var originalFetch = window.fetch ? window.fetch.bind(window) : null;
  if (originalFetch) {
    window.fetch = function (input, init) {
      return originalFetch(input, init).then(function (response) {
        try {
          var url = typeof input === "string" ? input : ((input && input.url) || "");
          var requestMethod = (init && init.method) || (input && input.method) || "";
          var isValidateAccess = url.indexOf("/api/site-review/") !== -1 && url.indexOf("/validate-access") !== -1;
          if (isValidateAccess) {
            response.clone().json().then(function (payload) {
              if (isOauthActionPayload(payload)) showOauthAction(payload);
            }).catch(function () {});
          }
        } catch (err) {}
        return response;
      });
    };
  }

  var OriginalXHR = window.XMLHttpRequest;
  if (OriginalXHR) {
    window.XMLHttpRequest = function () {
      var xhr = new OriginalXHR();
      var requestUrl = "";
      var originalOpen = xhr.open;
      xhr.open = function (method, url) {
        requestUrl = String(url || "");
        return originalOpen.apply(xhr, arguments);
      };
      xhr.addEventListener("load", function () {
        try {
          if (requestUrl.indexOf("/api/site-review/") !== -1 && requestUrl.indexOf("/validate-access") !== -1) {
            var payload = JSON.parse(xhr.responseText || "{}");
            if (isOauthActionPayload(payload)) showOauthAction(payload);
          }
        } catch (err) {}
      });
      return xhr;
    };
  }

  document.addEventListener("click", function (event) {
    var target = event.target && event.target.closest ? event.target.closest("button, a") : null;
    if (!target) return;
    var label = String(target.textContent || target.getAttribute("aria-label") || "").toLowerCase();
    if (label.indexOf("validate access") === -1) return;
    window.setTimeout(function () {
      if (window.__jomLatestValidateAccessOauthPayload) {
        showOauthAction(window.__jomLatestValidateAccessOauthPayload);
      }
    }, 250);
  }, true);
})();
// === Estate Validate Access OAuth Action Exact Handler Repair v1 END ===
// === Estate OAuth Completion Polling v1 START ===
(function () {
  "use strict";
  if (window.__jomEstateOauthCompletionPollingWired) return;
  window.__jomEstateOauthCompletionPollingWired = true;

  function currentReviewSiteKey() {
    var match = String(window.location.pathname || "").match(/\/estate\/review\/([^\/]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function showCompletionMessage(text, ok) {
    var existing = document.getElementById("jom-estate-oauth-completion-status-v1");
    if (existing) existing.remove();
    var box = document.createElement("section");
    box.id = "jom-estate-oauth-completion-status-v1";
    box.setAttribute("role", "status");
    box.style.border = ok ? "1px solid rgba(34, 197, 94, 0.45)" : "1px solid rgba(245, 158, 11, 0.50)";
    box.style.background = ok ? "rgba(34, 197, 94, 0.08)" : "rgba(245, 158, 11, 0.10)";
    box.style.borderRadius = "14px";
    box.style.padding = "14px";
    box.style.margin = "12px 0";
    box.textContent = text;
    var container = document.querySelector("aside") || document.querySelector("main") || document.body;
    container.appendChild(box);
  }

  function completeOauthValidation() {
    var siteKey = currentReviewSiteKey();
    if (!siteKey || !window.fetch) return Promise.resolve(false);
    return fetch("/api/site-review/" + encodeURIComponent(siteKey) + "/oauth-complete", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({actor: "site-review-oauth-complete"})
    }).then(function (response) {
      return response.clone().json().then(function (payload) {
        if (payload && payload.ok) {
          showCompletionMessage("Atlassian access validated. You can now enable monitoring.", true);
          return true;
        }
        return false;
      }).catch(function () { return false; });
    }).catch(function () { return false; });
  }

  window.jomEstateCompleteOauthValidation = completeOauthValidation;

  window.addEventListener("focus", function () {
    window.setTimeout(completeOauthValidation, 600);
  });

  document.addEventListener("click", function (event) {
    var target = event.target && event.target.closest ? event.target.closest("button, a") : null;
    if (!target) return;
    var label = String(target.textContent || target.getAttribute("aria-label") || "").toLowerCase();
    if (label.indexOf("authorise atlassian access") === -1 && label.indexOf("authorize atlassian access") === -1) return;
    window.setTimeout(function () {
      showCompletionMessage("Waiting for Atlassian authorisation to complete. Return to this page after authorising.", false);
    }, 250);
  }, true);

  if (String(window.location.search || "").indexOf("oauth") !== -1) {
    window.setTimeout(completeOauthValidation, 800);
  }
})();
// === Estate OAuth Completion Polling v1 END ===

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

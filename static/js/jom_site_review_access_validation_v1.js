
// JOM_SITE_REVIEW_VALID_ACCESS_ENABLE_UNLOCK_V1_ACCESS START
// Shared UI unlock after backend confirms OAuth/access coverage is valid.
function jomUnlockEnableMonitoringWhenAccessValid(){
  var enableButton = document.querySelector('[data-enable-monitoring]');
  var validateButton = document.querySelector('[data-validate-access], [data-start-auth]');
  if(validateButton){
    validateButton.hidden = true;
    validateButton.setAttribute('aria-hidden','true');
    validateButton.style.display = 'none';
  }
  if(enableButton){
    enableButton.hidden = false;
    enableButton.removeAttribute('hidden');
    enableButton.setAttribute('aria-hidden','false');
    enableButton.disabled = false;
    enableButton.removeAttribute('disabled');
    enableButton.removeAttribute('aria-disabled');
    enableButton.style.display = '';
    enableButton.style.pointerEvents = 'auto';
    enableButton.style.cursor = 'pointer';
  }
}
// JOM_SITE_REVIEW_VALID_ACCESS_ENABLE_UNLOCK_V1_ACCESS END
// JOM Site Review Access Validation v1 - single owner
// Single-refresh repair: avoid repeated post-load UI repaint cycles.
(function(){
  'use strict';
  const siteKey=document.body.getAttribute('data-site-key')||'';
  const $=id=>document.getElementById(id);
  async function getJson(url){
    const r=await fetch(url,{cache:'no-store'});
    const j=await r.json().catch(()=>({}));
    if(!r.ok)throw new Error(j.error||j.message||url+' failed');
    return j;
  }
  async function postJson(url,payload){
    const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload||{})});
    const j=await r.json().catch(()=>({}));
    if(!r.ok&&!(j&&j.action==='open_authorization_url'))throw new Error(j.error||j.message||url+' failed');
    return j;
  }
  function status(t,s){
    const e=$('site-review-validation-status');
    if(e){e.textContent=t;if(s)e.setAttribute('data-state',s);}
  }
  function enable(){return document.querySelector('[data-enable-monitoring]');}
  function validate(){return document.querySelector('[data-validate-access]');}
  const esc=v=>String(v??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
  function gate(v){
    const b=enable();
    const ok=v&&v.access_valid===true;
    const mon=b&&/monitoring enabled/i.test(b.textContent||'');
    if(b&&!mon&&b.style.display!=='none')b.disabled=!ok;
    if(ok){removePrompt();jomUnlockEnableMonitoringWhenAccessValid();status('Access validated. Monitoring can be enabled in JOM.','ok');}
    else if(v&&v.status)status('Access validation required before monitoring can be enabled. Current status: '+v.status+'. '+(v.reason||''),v.status==='ok'?'ok':'blocked');
    else status('Credential access has not been validated yet. Click Validate Access before enabling monitoring.','blocked');
  }
  function removePrompt(){const e=$('jom-estate-validate-access-oauth-action-v1');if(e)e.remove();}
  function prompt(p){
    if(!p||p.action!=='open_authorization_url'||!p.authorization_url)return;
    removePrompt();
    const box=document.createElement('section');
    box.id='jom-estate-validate-access-oauth-action-v1';
    box.setAttribute('role','dialog');
    box.style.position='fixed';box.style.inset='0';box.style.zIndex='10000';box.style.display='grid';box.style.placeItems='center';box.style.background='rgba(15,23,42,0.36)';
    box.innerHTML='<div style="max-width:520px;background:#fff;border-radius:18px;padding:24px;box-shadow:0 24px 70px rgba(9,30,66,.24)"><h2>Atlassian authorisation required</h2><p>'+esc(p.message||'Authorise Atlassian access before validating this site for monitoring.')+'</p><div style="display:flex;gap:10px;justify-content:flex-end"><button type="button" id="jom-oauth-cancel">Cancel</button><button type="button" id="jom-oauth-open">Authorise Atlassian Access</button></div></div>';
    document.body.appendChild(box);
    $('jom-oauth-cancel').addEventListener('click',removePrompt);
    $('jom-oauth-open').addEventListener('click',()=>{window.open(p.authorization_url,'_blank','noopener,noreferrer');status('Waiting for Atlassian authorisation to complete. Return to this page after authorising.','pending');});
  }
  async function refresh(){
    try{const p=await getJson('/api/site-review/'+encodeURIComponent(siteKey)+'/access-validation');gate(p.validation||{});}
    catch(e){status('Credential validation status unavailable: '+e.message,'failed');const b=enable();if(b)b.disabled=true;}
  }
  async function complete(showPrompt){
    try{
      const p=await postJson('/api/site-review/'+encodeURIComponent(siteKey)+'/oauth-complete',{actor:'site-review-oauth-complete'});
      if(p&&p.ok){removePrompt();gate(p.validation||{});return true;}
      if(showPrompt===true&&p&&p.action==='open_authorization_url')prompt(p);
    }catch(_e){}
    return false;
  }
  function wire(){
    const v=validate();
    if(v&&!v.dataset.validationWired){
      v.dataset.validationWired='true';
      v.addEventListener('click',async()=>{
        try{
          v.disabled=true;
          status('Validating Atlassian access using backend credentials...','pending');
          const p=await postJson('/api/site-review/'+encodeURIComponent(siteKey)+'/validate-access',{actor:'operator'});
          if(p&&p.action==='open_authorization_url')prompt(p);
          gate(p.validation||{});
        }catch(e){
          status('Access validation failed: '+e.message,'failed');
          const b=enable();if(b)b.disabled=true;
        }finally{v.disabled=false;}
      });
    }
    refresh();
    window.addEventListener('focus',()=>setTimeout(refresh,600));
    if(String(location.search||'').includes('oauth'))setTimeout(()=>complete(false),800);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',wire);else wire();
})();
// JOM Site Review Access Validation Single Refresh v1 START
// Removed automatic 800ms and 2000ms post-load refreshes to prevent visible page settling/repaint.
// JOM Site Review Access Validation Single Refresh v1 END

// JOM_OAUTH_CALLBACK_MODAL_CLOSE_REPAIR_V1_1



// JOM Estate Manage v1
(function(){
  'use strict';
  const siteKey = document.body.getAttribute('data-site-key') || '';
  const result = document.getElementById('estate-manage-result');
  function setResult(text){ if(result) result.textContent = text; }
  async function postJson(url, payload){
    const response = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload || {})});
    const body = await response.json();
    if(!response.ok) throw new Error(body.error || body.message || url + ' failed');
    return body;
  }
  function wire(){
    const button = document.querySelector('[data-revoke-monitoring]');
    if(!button) return;
    button.addEventListener('click', async function(){
      try{
        button.disabled = true;
        setResult('Revoking monitoring...');
        const payload = await postJson('/api/estate/manage/' + encodeURIComponent(siteKey) + '/revoke-monitoring', {actor:'operator'});
        setResult(payload.message || 'Monitoring revoked. This site will return to Discovery Review Queue.');
        setTimeout(function(){ window.location.href = '/estate'; }, 700);
      }catch(error){
        setResult('Revoke monitoring failed: ' + error.message);
        button.disabled = false;
      }
    });
  }
  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', wire); else wire();
})();

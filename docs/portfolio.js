(() => {
 'use strict';
 const script=document.currentScript, product=script.dataset.product, language=document.documentElement.lang==='ja'?'ja':'en';
 const endpoint='https://ai-meeting-broker-pdygkns5gq-an.a.run.app/api/site/';
 const words=(ja,en)=>language==='ja'?ja:en;
 const allowed=new Set(['demo_start','demo_complete','artifact_open','artifact_download','github_outbound','quickstart_open']);
 let budget=40;
 function event(name){if(!allowed.has(name)||budget<=0||navigator.doNotTrack==='1'||navigator.globalPrivacyControl)return;budget--;void fetch(endpoint+'events',{method:'POST',headers:{'content-type':'application/json'},credentials:'omit',referrerPolicy:'no-referrer',keepalive:true,body:JSON.stringify({event:name,scenario:product,language})}).catch(()=>{});}
 window.productEvent=event;
 document.addEventListener('click',e=>{const a=e.target.closest('a');if(!a||a.dataset.track)return;const href=a.getAttribute('href')||'';if(a.download||/\.zip(?:$|\?)/.test(href))event('artifact_download');else if(/github\.com/.test(href))event(/TESTING|README|quickstart/.test(href)?'quickstart_open':'github_outbound');else if(/#start|#quickstart/.test(href))event('quickstart_open');else if(a.dataset.artifact||/orbit\.html|kit-site/.test(href))event('artifact_open');});
 if(product!=='agent-team')document.querySelectorAll('video,audio').forEach(v=>{let started=false;v.addEventListener('play',()=>{if(!started){event('demo_start');started=true;}document.querySelectorAll('video,audio').forEach(o=>{if(o!==v)o.pause()});});v.addEventListener('ended',()=>event('demo_complete'));});
 document.addEventListener('visibilitychange',()=>{if(document.hidden)document.querySelectorAll('video,audio').forEach(v=>v.pause())});
 const form=document.getElementById('portfolio-form');if(!form)return;
 const status=document.getElementById('portfolio-status');let pending=false,id=crypto.randomUUID(),last='';
 form.addEventListener('submit',async e=>{
  e.preventDefault();if(pending||!form.reportValidity())return;
  const f=new FormData(form),body={name:String(f.get('name')||'').trim(),email:String(f.get('email')||'').trim(),organization:String(f.get('organization')||'').trim(),useCase:product,message:String(f.get('message')||'').trim(),consent:f.get('consent')==='on',website:String(f.get('website')||''),language};
  if(!body.name||body.message.length<10){status.textContent=words('お名前と10文字以上の相談内容を入力してください。','Please enter your name and at least 10 characters about your request.');return;}
  const fingerprint=JSON.stringify(body);if(last&&fingerprint!==last)id=crypto.randomUUID();last=fingerprint;
  const button=form.querySelector('button[type=submit]');pending=true;button.disabled=true;status.textContent=words('送信しています…','Sending…');
  try{const r=await fetch(endpoint+'leads',{method:'POST',headers:{'content-type':'application/json'},credentials:'omit',referrerPolicy:'no-referrer',body:JSON.stringify({...body,requestId:id}),signal:AbortSignal.timeout(15000)});const result=await r.json();if(!r.ok||typeof result.receipt!=='string')throw Error();status.textContent=words('非公開で受け付けました。受付番号：','Your private inquiry was received. Reference: ')+result.receipt;form.reset();id=crypto.randomUUID();last='';}
  catch{status.textContent=words('送信できませんでした。入力は保持しています。時間をおいて再度お試しください。','Could not send. Your input is preserved; please try again shortly.');}
  finally{pending=false;button.disabled=false;}
 });
})();
(() => {
 'use strict';
 const script=document.currentScript, product=script.dataset.product, language=document.documentElement.lang==='ja'?'ja':'en';
 const endpoint='https://ai-meeting-broker-pdygkns5gq-an.a.run.app/api/site/';
 const words=(ja,en)=>language==='ja'?ja:en;
 const allowed=new Set(['demo_start','demo_complete','example_open','artifact_open','artifact_download','github_outbound','quickstart_open','quickstart_copy','record_finding','contact_submit']);
 // The deployed collector currently accepts only this subset. Keep the full
 // local dataLayer vocabulary for UX/QA, but do not create repeated 400s for
 // events that the collector has not enabled yet.
 const remoteAllowed=new Set(['demo_start','demo_complete','artifact_open','artifact_download','github_outbound','quickstart_open']);
 const localHost=location.hostname==='localhost'||location.hostname==='127.0.0.1'||location.hostname==='[::1]';
 let budget=40;
 window.dataLayer=window.dataLayer||[];
 function event(name,props){if(!allowed.has(name)||budget<=0||navigator.doNotTrack==='1'||navigator.globalPrivacyControl)return;budget--;window.dataLayer.push({event:name,kind:props&&props.kind,scenario:product,language});if(localHost||!remoteAllowed.has(name))return;void fetch(endpoint+'events',{method:'POST',headers:{'content-type':'application/json'},credentials:'omit',referrerPolicy:'no-referrer',keepalive:true,body:JSON.stringify({event:name,scenario:product,language})}).catch(()=>{});}
 window.productEvent=event;
 document.addEventListener('click',e=>{const a=e.target.closest('a');if(!a)return;if(a.dataset.track){if(!a.closest('[data-record]'))event(a.dataset.track,{href:a.href,intent:a.getAttribute('data-intent')||undefined});return;}const href=a.getAttribute('href')||'';if(a.download||/\.zip(?:$|\?)/.test(href))event('artifact_download');else if(/github\.com/.test(href))event(/TESTING|README|quickstart/.test(href)?'quickstart_open':'github_outbound');else if(/#start|#quickstart/.test(href))event('quickstart_open');else if(a.dataset.artifact||/orbit\.html|kit-site/.test(href))event('artifact_open');});
 document.querySelectorAll('video,audio').forEach(v=>{let started=false;v.addEventListener('play',()=>{if(!started){event('demo_start',{kind:'replay'});started=true;}document.querySelectorAll('video,audio').forEach(o=>{if(o!==v)o.pause()});});v.addEventListener('ended',()=>event('demo_complete',{kind:'replay'}));});
 document.addEventListener('visibilitychange',()=>{if(document.hidden)document.querySelectorAll('video,audio').forEach(v=>v.pause())});

 // Homepage signature: lead with the outcome of one saved run rather than with
 // "multi-agent" architecture. The record is explicitly labelled partial and
 // links back to the existing public evidence; it is not a new success claim.
 if(product==='agent-team'){
  const css=document.createElement('link');css.rel='stylesheet';css.href=new URL('outcome-proof.css',script.src).href;document.head.append(css);
  const hero=document.querySelector('.hero');
  const copy=hero&&hero.querySelector('.hero-copy');
  if(hero&&copy&&!hero.querySelector('.outcome-proof')){
   const proof=document.createElement('section');proof.className='outcome-proof';proof.setAttribute('aria-label',words('保存済み実行の流れ','Saved run flow'));
   const data=language==='ja'?{
    kicker:'REAL RUN / PARTIAL',title:'依頼から、レビューされたファイルまで。',truth:'2026-09-12〜13の保存済み実行。途中の確認が未完了のため、実行全体は部分完了です。',
    steps:[['01 / REQUEST','依頼','公開ページを比較'],['02 / DRAFT','初稿','research.md r1'],['03 / REVIEW','レビュー','3件の指摘'],['04 / REVISION','修正','指摘を反映'],['05 / FILE','成果物','research-final-r2.md']],
    primary:'実行記録を見る',secondary:'成果物と制約を開く',note:'成功率や一般的な品質優位を示す例ではありません。'
   }:{
    kicker:'REAL RUN / PARTIAL',title:'From one request to a reviewed file.',truth:'A saved 2026-09-12–13 execution. The overall run ended partial because one verification remained unfinished.',
    steps:[['01 / REQUEST','Request','Compare public pages'],['02 / DRAFT','Draft','research.md r1'],['03 / REVIEW','Review','3 findings'],['04 / REVISION','Revision','Apply findings'],['05 / FILE','Deliverable','research-final-r2.md']],
    primary:'Open the work record',secondary:'Open artifacts and limits',note:'This example is not a measured success rate or a claim of general quality superiority.'
   };
   proof.innerHTML='<div class="outcome-proof__head"><div><p class="outcome-proof__kicker">'+data.kicker+'</p><h2>'+data.title+'</h2></div><p class="outcome-proof__truth">'+data.truth+'</p></div><div class="outcome-proof__flow">'+data.steps.map((s,i)=>'<div class="outcome-proof__step'+(i===data.steps.length-1?' outcome-proof__step--file':'')+'"><span>'+s[0]+'</span><strong>'+s[1]+'</strong><p>'+s[2]+'</p></div>').join('')+'</div><div class="outcome-proof__links"><a href="#record" data-track="example_open">'+data.primary+' →</a><a href="https://github.com/FORIFOR/Multibot/tree/main/docs/evidence/scenarios/research2" data-track="artifact_open">'+data.secondary+' ↗</a><small>'+data.note+'</small></div>';
   copy.after(proof);
  }
 }

 const form=document.getElementById('portfolio-form');if(!form)return;
 const status=document.getElementById('portfolio-status');let pending=false,id=crypto.randomUUID(),last='';
 form.addEventListener('submit',async e=>{
  e.preventDefault();if(pending||!form.reportValidity())return;
  const f=new FormData(form),body={name:String(f.get('name')||'').trim(),email:String(f.get('email')||'').trim(),organization:String(f.get('organization')||'').trim(),useCase:product,message:String(f.get('message')||'').trim(),consent:f.get('consent')==='on',website:String(f.get('website')||''),language};
  if(!body.name||body.message.length<10){status.textContent=words('お名前と10文字以上の相談内容を入力してください。','Please enter your name and at least 10 characters about your request.');return;}
  const fingerprint=JSON.stringify(body);if(last&&fingerprint!==last)id=crypto.randomUUID();last=fingerprint;
  const button=form.querySelector('button[type=submit]');pending=true;button.disabled=true;status.textContent=words('送信しています…','Sending…');
  try{const r=await fetch(endpoint+'leads',{method:'POST',headers:{'content-type':'application/json'},credentials:'omit',referrerPolicy:'no-referrer',body:JSON.stringify({...body,requestId:id}),signal:AbortSignal.timeout(15000)});const result=await r.json();if(!r.ok||typeof result.receipt!=='string')throw Error();status.textContent=words('非公開で受け付けました。受付番号：','Your private inquiry was received. Reference: ')+result.receipt;event('contact_submit');form.reset();id=crypto.randomUUID();last='';}
  catch{status.textContent=words('送信できませんでした。入力は保持しています。時間をおいて再度お試しください。','Could not send. Your input is preserved; please try again shortly.');}
  finally{pending=false;button.disabled=false;}
 });
})();
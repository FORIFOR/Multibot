import {chromium} from 'playwright-core';
import {readFileSync,writeFileSync} from 'node:fs';
import assert from 'node:assert/strict';
const out=process.env.QUALITY_OUT || '../artifacts/product-quality/trading-team-round2';
const base=process.env.QUALITY_BASE || 'http://127.0.0.1:8802';
const id=readFileSync(`${out}/run-id.txt`,'utf8').trim();
const browser=await chromium.launch({channel:'chrome'});
try {
  const context=await browser.newContext({locale:'ja-JP',viewport:{width:1440,height:1000}});
  const read=async path=>{const r=await context.request.get(base+path);assert.ok(r.ok());return r.json();};
  const path=`/api/runs/${id}`,before=await read(path),chat=await read(path+'/chat');
  assert.equal(before.live,false,'Never resume a live operation');
  assert.equal(before.status,'interrupted','This check is for a confirmed interruption');
  writeFileSync(`${out}/before-resume.json`,JSON.stringify(before,null,2));
  const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(`${base}/runs/${id}?view=conversation`);
  await page.locator('.desk-resume summary').click();
  const receipt=page.waitForResponse(r=>r.url()===base+path+'/resume'&&r.request().method()==='POST');
  await page.getByRole('button',{name:'確認して再開',exact:true}).click();
  const response=await receipt;assert.ok(response.ok());
  let after=await read(path);
  for(let i=0;i<40&&!(after.live&&after.last_seq>before.last_seq);i++){
    await page.waitForTimeout(250);after=await read(path);
  }
  assert.ok(after.live&&after.last_seq>before.last_seq);
  assert.equal(after.run_id,id);
  for(const a of before.artifacts)assert.ok(after.artifacts.some(b=>b.artifact_id===a.artifact_id&&b.revision===a.revision&&b.sha256===a.sha256));
  for(const [key,agent] of Object.entries(before.config_snapshot.agents))assert.equal(after.config_snapshot.agents[key].speech_style,agent.speech_style);
  const currentChat=await read(path+'/chat');
  for(const m of chat)assert.ok(currentChat.some(n=>n.event_id===m.event_id&&n.text===m.text));
  assert.equal(currentChat.filter(m=>m.from==='master').length,chat.filter(m=>m.from==='master').length,'Coordinator must not resend existing handoffs');
  await page.reload();await page.getByRole('heading',{name:'チームの会話',exact:true}).waitFor();
  await page.screenshot({path:`${out}/resumed.png`,fullPage:true});
  assert.deepEqual(errors,[]);
  writeFileSync(`${out}/resumed.json`,JSON.stringify(after,null,2));
  writeFileSync(`${out}/resume-observation.json`,JSON.stringify({runId:id,browser:browser.version(),sameRun:true,voicesPreserved:true,artifactsPreserved:true,messagesPreserved:true,noCoordinatorResend:true,errors},null,2));
  console.log('PASS actual UI resume, same run, preserved voices/messages/artifact revisions; no coordinator resend. Content quality remains separately unverified.');
} finally {await browser.close();}

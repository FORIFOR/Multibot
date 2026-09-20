import {chromium} from 'playwright-core'
import assert from 'node:assert/strict'
import {mkdirSync,writeFileSync} from 'node:fs'
const out='../artifacts/product-quality/elapsed';mkdirSync(out,{recursive:true})
const b=await chromium.launch({channel:'chrome',headless:true}),c=await b.newContext({locale:'ja-JP',viewport:{width:390,height:844}}),p=await c.newPage(),results=[]
const value=async()=>Number((await p.locator('.conversation-elapsed time').getAttribute('datetime')).match(/PT(\d+)S/)[1])
try {
 for(const id of ['run_1a0b982c5bc72cef6bb','run_1a0b9570af7d0142694']){
  const r=await(await c.request.get(`http://127.0.0.1:8796/api/runs/${id}`)).json();await p.goto(`http://127.0.0.1:8796/runs/${id}?view=conversation`);await p.locator('.conversation-elapsed time').waitFor();const before=await value();await p.waitForTimeout(2200);const after=await value();
  if(r.live&&!r.finished_at){assert.ok(after>before);assert.ok(Math.abs(after-Math.floor((Date.now()-Date.parse(r.started_at))/1000))<4)}else{assert.equal(after,before);if(r.finished_at)assert.equal(after,Math.floor((Date.parse(r.finished_at)-Date.parse(r.started_at))/1000))}
  assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await p.locator('.conversation-elapsed').scrollIntoViewIfNeeded();await p.screenshot({path:`${out}/${id}.png`});results.push({id,status:r.status,live:r.live,before,after})
 }
 writeFileSync(`${out}/browser.json`,JSON.stringify(results,null,2));console.log('PASS actual start/end duration, ticking vs stopped, 390px')
}finally{await c.close();await b.close()}

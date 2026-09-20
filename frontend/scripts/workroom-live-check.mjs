import { chromium } from 'playwright-core'
import assert from 'node:assert/strict'
import { mkdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
const out=resolve('../artifacts/product-quality/workroom-live');mkdirSync(out,{recursive:true})
const b=await chromium.launch({channel:'chrome',headless:true});const results=[]
try{
 for(const [base,id] of [['http://127.0.0.1:8796','run_1a0b9570af7d0142694'],['http://127.0.0.1:8798','run_1a09c8485503d406bf4']]){
  const c=await b.newContext({viewport:{width:1440,height:1000},locale:'ja-JP',reducedMotion:'reduce'}),p=await c.newPage(),errors=[],writes=[]
  p.on('pageerror',e=>errors.push(e.message));p.on('request',r=>{if(r.method()!=='GET')writes.push(r.method()+' '+r.url())})
  const chat=await (await c.request.get(`${base}/api/runs/${id}/chat`)).json()
  await p.goto(`${base}/runs/${id}`);await p.locator('.work-progress-disclosure > summary').click();await p.getByRole('region',{name:'作業の状態遷移',exact:true}).waitFor()
  assert.equal(await p.locator('.phase-track li').count(),5)
  for(const m of chat)assert.equal(await p.locator(`[data-message-id="${m.event_id}"] .message-text`).textContent(),m.text)
  await p.getByRole('button',{name:'最新を自動追従',exact:true}).click();assert.equal(await p.getByRole('log').getAttribute('aria-live'),'off')
  await p.getByRole('button',{name:'最新へ戻る',exact:true}).focus();await p.keyboard.press('Enter');assert.equal(await p.getByRole('log').getAttribute('aria-live'),'polite')
  await p.getByText('状態が変わった履歴を見る',{exact:true}).click();assert.ok(await p.locator('.stage-history li').count()>0)
  await p.getByText('状態が変わった履歴を見る',{exact:true}).click()
  for(const width of [1440,768,390]){
   await p.setViewportSize({width,height:1000});await p.screenshot({path:`${out}/${id}-${width}.png`,fullPage:true})
   assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false)
  }
  if(base.endsWith('8796')){
   await c.setOffline(true);await p.getByRole('alert').filter({hasText:'最新の状態を取得できません'}).waitFor({timeout:12000})
   await c.setOffline(false);await p.getByRole('alert').filter({hasText:'最新の状態を取得できません'}).waitFor({state:'hidden',timeout:15000})
  }
  assert.deepEqual(errors,[]);assert.deepEqual(writes,[])
  results.push({id,chat_count:chat.length,raw_text_matches:true,widths:[1440,768,390],follow_keyboard:true,errors,writes})
  await c.close()
 }
 writeFileSync(`${out}/browser-check.json`,JSON.stringify({browser:b.version(),results},null,2));console.log(JSON.stringify(results))
}finally{await b.close()}

import {chromium} from 'playwright-core'
import AxeBuilder from '@axe-core/playwright'
import assert from 'node:assert/strict'
import {mkdirSync,writeFileSync} from 'node:fs'
const out='../artifacts/product-quality/simple-chat';mkdirSync(out,{recursive:true})
const b=await chromium.launch({channel:'chrome',headless:true}), result={errors:[],writes:[],violations:[],chat:0}
try {
 const c=await b.newContext({locale:'ja-JP',viewport:{width:1440,height:1000},reducedMotion:'reduce'}),p=await c.newPage();p.on('pageerror',e=>result.errors.push(e.message));p.on('request',r=>{if(r.method()!=='GET')result.writes.push(r.method())})
 for(const [base,id] of [['http://127.0.0.1:8796','run_1a0b982c5bc72cef6bb'],['http://127.0.0.1:8798','run_1a09c8485503d406bf4']]){
  await p.goto(`${base}/runs/${id}?view=conversation`);await p.locator('.live-conversation').waitFor();assert.equal(await p.locator('.conversation-caption').count(),0)
  for(const selector of ['.work-progress-disclosure','.conversation-activity','.simple-request']) {assert.equal(await p.locator(selector).getAttribute('open'),null);await p.locator(`${selector} > summary`).focus();await p.keyboard.press('Enter');assert.notEqual(await p.locator(selector).getAttribute('open'),null);await p.keyboard.press('Enter')}
  const chat=await(await c.request.get(`${base}/api/runs/${id}/chat`)).json();for(const m of chat)assert.equal(await p.locator(`[data-message-id="${m.event_id}"] .message-text`).textContent(),m.text);result.chat+=chat.length
  for(const width of [1440,390]){await p.setViewportSize({width,height:1000});await p.locator('#work-conversation').scrollIntoViewIfNeeded();assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await p.screenshot({path:`${out}/${id}-${width}.png`});const a=await new AxeBuilder({page:p}).include('.live-conversation').withTags(['wcag2a','wcag2aa']).analyze();result.violations.push(...a.violations)}
 }
 assert.deepEqual(result.errors,[]);assert.deepEqual(result.writes,[]);assert.deepEqual(result.violations,[]);writeFileSync(`${out}/browser.json`,JSON.stringify(result,null,2));console.log('PASS collapsible details, real chat preservation, 1440/390, scoped axe and GET only');await c.close()
} finally {await b.close()}

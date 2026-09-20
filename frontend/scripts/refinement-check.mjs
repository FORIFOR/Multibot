import {chromium} from 'playwright-core'
import AxeBuilder from '@axe-core/playwright'
import assert from 'node:assert/strict'
import {mkdirSync,writeFileSync} from 'node:fs'
const out='../artifacts/product-quality/ui-refinement';mkdirSync(out,{recursive:true})
const b=await chromium.launch({channel:'chrome',headless:true}),c=await b.newContext({locale:'ja-JP',viewport:{width:1440,height:1000},reducedMotion:'reduce'}),p=await c.newPage(),result={errors:[],writes:[],violations:[],chat:0}
p.on('pageerror',e=>result.errors.push(e.message));p.on('request',r=>{if(r.method()!=='GET')result.writes.push(r.method())})
try {
 for(const [base,id] of [['http://127.0.0.1:8796','run_1a0b982c5bc72cef6bb'],['http://127.0.0.1:8798','run_1a09c8485503d406bf4']]){
 await p.goto(`${base}/runs/${id}?view=conversation`);await p.locator('.live-conversation').waitFor();assert.equal(await p.locator('.conversation-context').count(),0);assert.equal(await p.locator('.work-back').count(),1)
 const chat=await(await c.request.get(`${base}/api/runs/${id}/chat`)).json();for(const m of chat)assert.equal(await p.locator(`[data-message-id="${m.event_id}"] .message-text`).textContent(),m.text);result.chat+=chat.length
 for(const label of ['成果物','会話']){const button=p.locator('.room-view-nav button').filter({hasText:label});await button.focus();await p.keyboard.press('Enter');assert.equal(await button.getAttribute('aria-current'),'location');assert.equal(await p.evaluate(()=>document.activeElement.id),label==='会話'?'work-conversation':'room-results')}
 for(const width of [1440,768,390]){await p.setViewportSize({width,height:1000});await p.evaluate(()=>scrollTo(0,0));assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await p.screenshot({path:`${out}/${id}-${width}.png`,fullPage:true})}
 const scan=await new AxeBuilder({page:p}).include('.simple-workroom').exclude('#room-results').withTags(['wcag2a','wcag2aa']).analyze();result.violations.push(...scan.violations)
 // 200% CSS zoom exercises layout scaling; not OS/browser menu zoom.
 await p.setViewportSize({width:1440,height:1000});await p.evaluate(()=>document.documentElement.style.zoom='2');assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await p.evaluate(()=>document.documentElement.style.zoom='1')
 }
 assert.deepEqual(result.errors,[]);assert.deepEqual(result.writes,[]);writeFileSync(`${out}/browser.json`,JSON.stringify(result,null,2));assert.deepEqual(result.violations,[]);console.log('PASS responsive layout, keyboard navigation, original chat, 200% CSS zoom and scoped axe')
} finally{await c.close();await b.close()}

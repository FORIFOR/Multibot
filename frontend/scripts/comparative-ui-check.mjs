import {chromium} from 'playwright-core'
import AxeBuilder from '@axe-core/playwright'
import assert from 'node:assert/strict'
import {readFileSync,writeFileSync} from 'node:fs'
const out='../artifacts/product-quality/comparative-ui',b=await chromium.launch({channel:'chrome',headless:true}),c=await b.newContext({locale:'ja-JP',viewport:{width:1440,height:1000},reducedMotion:'reduce'}),p=await c.newPage(),result={errors:[],writes:[],violations:[]}
p.on('pageerror',e=>result.errors.push(e.message));p.on('request',r=>{if(r.method()!=='GET')result.writes.push(r.method())})
try {
 const base='http://127.0.0.1:8796',runs=await(await c.request.get(base+'/api/runs')).json();await p.goto(base+'/runs');await p.locator('.work-item').first().waitFor();const q=runs[0].goal
 await p.getByRole('searchbox',{name:'作業を検索'}).fill(q);assert.equal(await p.locator('.work-item').count(),runs.filter(r=>r.goal.toLowerCase().includes(q.toLowerCase())).length)
 await p.reload();await p.locator('.work-item').first().waitFor();assert.equal(await p.getByRole('searchbox').inputValue(),q)
 await p.getByRole('button',{name:'クリア',exact:true}).click();assert.equal(await p.locator('.work-item').count(),runs.length)
 await p.goto('http://127.0.0.1:8798/runs/run_1a09c8485503d406bf4?view=conversation');await p.locator('.conversation-message').waitFor();const original=await p.locator('.message-text').textContent()
 await p.locator('.conversation-filters > summary').click();await p.getByRole('searchbox',{name:'会話を検索'}).fill(original.slice(0,20));assert.equal(await p.locator('.message-text').textContent(),original);assert.equal(await p.getByRole('log').getAttribute('aria-live'),'off')
 await p.getByRole('combobox',{name:'担当で絞り込み'}).selectOption('reviewer');assert.equal(await p.locator('.conversation-message').count(),1)
 await p.getByRole('searchbox',{name:'会話を検索'}).fill(readFileSync('../docs/quality/comparative-ui.md','utf8').split('\n')[0]);assert.equal(await p.locator('.conversation-message').count(),0)
 await p.getByRole('button',{name:'絞り込みを解除'}).click();assert.equal(await p.locator('.message-text').textContent(),original)
 for(const width of [1440,390]){await p.setViewportSize({width,height:1000});await p.locator('.conversation-filters').scrollIntoViewIfNeeded();assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await p.screenshot({path:`${out}/chat-${width}.png`});const a=await new AxeBuilder({page:p}).include('.live-conversation').withTags(['wcag2a','wcag2aa']).analyze();result.violations.push(...a.violations)}
 assert.deepEqual(result.errors,[]);assert.deepEqual(result.writes,[]);assert.deepEqual(result.violations,[]);writeFileSync(`${out}/browser.json`,JSON.stringify(result,null,2));console.log('PASS real request search/reload/clear, participant/text filters, zero-match recovery, exact original text, widths and axe')
}finally{await c.close();await b.close()}

import {chromium} from 'playwright-core'
import AxeBuilder from '@axe-core/playwright'
import assert from 'node:assert/strict'
import {mkdirSync,writeFileSync} from 'node:fs'
const out='../artifacts/product-quality/conversation-processing';mkdirSync(out,{recursive:true})
const b=await chromium.launch({channel:'chrome',headless:true}), evidence={browser:b.version(),writes:[],errors:[],violations:[],states:[]}
try {
 const c=await b.newContext({locale:'ja-JP',viewport:{width:1440,height:1000}}),p=await c.newPage()
 p.on('pageerror',e=>evidence.errors.push(e.message));p.on('request',r=>{if(r.method()!=='GET')evidence.writes.push(r.method())})
 const id='run_1a0b982c5bc72cef6bb',url=`http://127.0.0.1:8796/runs/${id}?view=conversation`
 const run=await(await c.request.get(`http://127.0.0.1:8796/api/runs/${id}`)).json();evidence.states.push({status:run.status,live:run.live});assert.ok(['planning','running','created','queued'].includes(run.status)&&run.live,'Actual run must still be active')
 await p.goto(url);await p.locator('[data-processing="active"]').waitFor()
 assert.notEqual(await p.locator('.processing-dots i').first().evaluate(e=>getComputedStyle(e).animationName),'none')
 for(const width of [1440,390]){await p.setViewportSize({width,height:1000});await p.locator('.conversation-processing').scrollIntoViewIfNeeded();assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await p.screenshot({path:`${out}/active-${width}.png`});const scan=await new AxeBuilder({page:p}).include('.conversation-processing').withTags(['wcag2a','wcag2aa']).analyze();evidence.violations.push(...scan.violations)}
 await p.emulateMedia({reducedMotion:'reduce'});assert.equal(await p.locator('.processing-dots i').first().evaluate(e=>getComputedStyle(e).animationName),'none')
 await p.emulateMedia({reducedMotion:'no-preference'});await p.getByRole('button',{name:'動きを止める',exact:true}).click();assert.equal(await p.locator('.processing-dots i').first().evaluate(e=>getComputedStyle(e).animationName),'none')
 await c.setOffline(true);await p.locator('[data-processing="waiting"]').waitFor({timeout:12000});assert.equal(await p.locator('.processing-dots i').first().evaluate(e=>getComputedStyle(e).animationName),'none');await c.setOffline(false);await p.locator('[data-processing="active"]').waitFor({timeout:15000})
 await p.goto('http://127.0.0.1:8796/runs/run_1a0b9570af7d0142694?view=conversation');await p.locator('.live-conversation').waitFor();assert.equal(await p.locator('.conversation-processing').count(),0)
 assert.deepEqual(evidence.errors,[]);assert.deepEqual(evidence.writes,[]);assert.deepEqual(evidence.violations,[]);writeFileSync(`${out}/browser.json`,JSON.stringify(evidence,null,2));console.log('PASS actual active run, interrupted run, animation, reduced motion, pause, disconnect/recovery, widths and scoped axe');await c.close()
} finally {await b.close()}

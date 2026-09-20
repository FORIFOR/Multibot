import { chromium } from 'playwright-core'
import AxeBuilder from '@axe-core/playwright'
import assert from 'node:assert/strict'
import {mkdirSync,writeFileSync} from 'node:fs'
const out='../artifacts/product-quality/work-list';mkdirSync(out,{recursive:true})
const browser=await chromium.launch({channel:'chrome',headless:true})
const evidence={browser:browser.version(),runs:[],widths:[],writes:[],errors:[],violations:[]}
try {
 const context=await browser.newContext({viewport:{width:1440,height:1000},locale:'ja-JP',reducedMotion:'reduce'})
 const page=await context.newPage();page.on('pageerror',e=>evidence.errors.push(e.message));page.on('request',r=>{if(r.method()!=='GET')evidence.writes.push(r.method()+' '+r.url())})
 const runs=await(await context.request.get('http://127.0.0.1:8796/api/runs')).json();evidence.runs=runs.map(r=>({id:r.run_id,status:r.status}))
 await page.goto('http://127.0.0.1:8796/runs');await page.locator('.work-items li').first().waitFor()
 const statuses={all:runs,active:runs.filter(r=>['created','queued','planning','running'].includes(r.status)),attention:runs.filter(r=>['approval_required','blocked'].includes(r.status)),completed:runs.filter(r=>r.status==='completed')}
 for(const [filter,expected] of Object.entries(statuses)) {
  const link=page.locator(`.work-filters a[href="/runs?filter=${filter}"]`);await link.focus();await page.keyboard.press('Enter');assert.equal(await link.getAttribute('aria-current'),'page');assert.equal(await page.locator('.work-items li').count(),expected.length)
  await page.reload();await page.locator('.work-list-count').waitFor();assert.equal(await page.locator('.work-items li').count(),expected.length)
 }
 await page.goBack();assert.ok(page.url().includes('attention'))
 await page.locator('.work-filters a[href="/runs?filter=all"]').click();await page.locator('.work-item').first().click();await page.locator('#work-conversation').waitFor();await page.waitForTimeout(200)
 assert.equal(await page.evaluate(()=>document.activeElement.id),'work-conversation')
 assert.equal(await page.evaluate(()=>window.scrollY),0) // Request context stays visible on entry.
 await page.locator('.work-back').click();assert.ok(page.url().includes('filter=all'))
 for(const width of [1440,768,390]) {
  await page.setViewportSize({width,height:1000});await page.evaluate(()=>scrollTo(0,0));assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false)
  const a=await new AxeBuilder({page}).include('.work-list').withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();evidence.violations.push(...a.violations)
  await page.screenshot({path:`${out}/list-${width}.png`,fullPage:true});evidence.widths.push(width)
 }
 await context.setOffline(true);await page.getByRole('alert').waitFor({timeout:12000});await context.setOffline(false);await page.getByRole('alert').waitFor({state:'hidden',timeout:12000})
 await page.goto('http://127.0.0.1:8798/runs');await page.locator('.work-item').first().click();await page.locator('.conversation-message').waitFor()
 const id=new URL(page.url()).pathname.split('/').at(-1);const chat=await(await context.request.get(`http://127.0.0.1:8798/api/runs/${id}/chat`)).json()
 for(const message of chat)assert.equal(await page.locator(`[data-message-id="${message.event_id}"] .message-text`).textContent(),message.text)
 evidence.real_chat_count=chat.length;await page.screenshot({path:`${out}/conversation-390.png`})
 assert.deepEqual(evidence.errors,[]);assert.deepEqual(evidence.writes,[]);assert.deepEqual(evidence.violations,[])
 writeFileSync(`${out}/browser.json`,JSON.stringify(evidence,null,2));console.log('PASS filters, navigation, focus, reload, recovery, real chat, widths and scoped axe')
 await context.close()
} finally {await browser.close()}

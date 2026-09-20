// Read and operate only the actual run created by product-quality-live.mjs.
import assert from 'node:assert/strict'
import { chromium } from 'playwright-core'
import { resolve } from 'node:path'
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import AxeBuilder from '@axe-core/playwright'
const base=process.env.QUALITY_BASE || 'http://127.0.0.1:8796', out=resolve(process.env.QUALITY_OUT || '../artifacts/product-quality')
assert.ok(['127.0.0.1','localhost'].includes(new URL(base).hostname))
mkdirSync(out,{recursive:true})
const runId=process.env.QUALITY_RUN_ID || readFileSync(`${out}/run-id.txt`,'utf8').trim()
const browser=await chromium.launch({channel:'chrome',headless:true}),observations=[],errors=[]
const note=(name,detail)=>{observations.push({name,detail});writeFileSync(`${out}/browser-results.json`,JSON.stringify({browser:browser.version(),observations,errors},null,2));console.log(name)}
try{
 for(const [width,lang] of [[1440,'ja'],[390,'ja'],[768,'ja'],[1100,'ja'],[1440,'en']]){
  const context=await browser.newContext({viewport:{width,height:1000},locale:lang==='ja'?'ja-JP':'en-US',reducedMotion:'reduce',acceptDownloads:true})
  await context.addInitScript(lang=>localStorage.setItem('agentteam.lang',lang),lang)
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message))
  await page.goto(base);await page.locator('.request-disclosure').waitFor()
  for(const location of ['home','workroom']){
   if(location==='workroom'){await page.goto(`${base}/runs/${runId}`);await page.locator('.result-reader').waitFor({timeout:600000})}
   const sizes=await page.evaluate(()=>({viewport:innerWidth,width:document.documentElement.scrollWidth}))
   assert.ok(sizes.width<=sizes.viewport+1,JSON.stringify({location,...sizes}))
   const scan=await new AxeBuilder({page}).exclude('iframe').withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()
   note(`${location} ${width} ${lang}`,{sizes,axe:scan.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>n.target)}))})
   await page.screenshot({path:`${out}/${location}-${width}-${lang}.png`,fullPage:true})
  }
  if(width===1440&&lang==='ja'){
   const reader=page.locator('.result-reader')
   await reader.focus();await page.keyboard.press('PageDown')
   const scrolling=await reader.evaluate(e=>({focused:document.activeElement===e,scrollTop:e.scrollTop,clientHeight:e.clientHeight,scrollHeight:e.scrollHeight}))
   assert.equal(scrolling.focused,true)
   // Wait for browser scroll animation only when the actual content needs scrolling.
   if(scrolling.scrollHeight>scrolling.clientHeight)await page.waitForFunction(()=>document.querySelector('.result-reader').scrollTop>0)
   note('keyboard result scrolling',scrolling)

   if(process.env.QUALITY_OLD_REVISION === '1'){
    await page.locator('#result-record > summary').click()
    await page.getByRole('button',{name:'版 1',exact:true}).click()
   }
   const adopt=page.locator('[data-adopt]')
   const adoptedByKeyboard=(await adopt.count())>0
   if(adoptedByKeyboard){
    await adopt.focus();await page.keyboard.press('Enter')
    await page.waitForFunction(()=>document.activeElement?.classList.contains('chosen-pill'))
    assert.equal(await page.locator('.chosen-pill').evaluate(e=>getComputedStyle(e).outlineStyle),'solid')
   }
   const detail=await (await context.request.get(`${base}/api/runs/${runId}`)).json()
   writeFileSync(`${out}/selected-run.json`,JSON.stringify(detail,null,2))
   const downloadPromise=page.waitForEvent('download')
   await page.getByRole('link',{name:'採用したファイルを保存'}).focus();await page.keyboard.press('Enter')
   const download=await downloadPromise;await download.saveAs(`${out}/selected-browser.zip`)
   await page.reload();await page.locator('.chosen-pill').waitFor()
   note('adoption and download',{adoptedByKeyboard,focusTransfer:adoptedByKeyboard ? 'chosen pill' : 'not repeated: version already selected',download:'browser ZIP saved via keyboard',persistence:'selection survives reload'})
   await page.screenshot({path:`${out}/selected-focus.png`,fullPage:true})
   await context.setOffline(true)
   // Wait for the real periodic GET to fail, leaving persisted result content visible.
   await page.getByText('最新の状態を取得できません。表示内容が古い可能性があります。',{exact:false}).first().waitFor({timeout:12000})
   await context.setOffline(false);await page.getByRole('button',{name:'再読み込み'}).click()
   await page.waitForFunction(()=>!document.body.textContent.includes('最新の状態を取得できません'))
   note('result reconnect','real network disconnection shows stale-state warning; explicit refresh recovers')
   await page.evaluate(()=>{document.documentElement.style.zoom='2'})
   const zoom=await page.evaluate(()=>({viewport:innerWidth,width:document.documentElement.scrollWidth,zoom:getComputedStyle(document.documentElement).zoom}))
   assert.ok(zoom.width<=zoom.viewport+1,JSON.stringify(zoom))
   await page.screenshot({path:`${out}/workroom-css-zoom200.png`,fullPage:true});note('200% CSS reflow',zoom)
   await page.evaluate(()=>{document.documentElement.style.zoom=''})
   note('reduced motion',await page.evaluate(()=>({requested:matchMedia('(prefers-reduced-motion: reduce)').matches,running:document.getAnimations().filter(a=>a.playState==='running'&&a.effect?.getTiming().iterations===Infinity).length})))
  }
  await context.close()
 }
 assert.deepEqual(errors,[])
 assert.ok(observations.filter(o=>o.detail?.axe).every(o=>o.detail.axe.length===0),'axe violations require investigation')
}finally{note('page exceptions',errors);await browser.close()}

// Test the newly built UI against the isolated scripted test backend, not an LLM.
import { chromium } from 'playwright-core'
import { mkdirSync, writeFileSync } from 'node:fs'
const base=process.env.BASE||'http://127.0.0.1:8791'
const shots='/tmp/workroom-shots';mkdirSync(shots,{recursive:true})
const browser=await chromium.launch({channel:'chrome',headless:true})
const report=[]
try {
  for(const width of [390,1440])for(const lang of ['ja','en']){
    const context=await browser.newContext({viewport:{width,height:900},locale:lang==='ja'?'ja-JP':'en-US',reducedMotion:'reduce'})
    const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message))
    await page.goto(base,{waitUntil:'networkidle'})
    const start=lang==='ja'?'開始':'Start'
    await page.locator('textarea').first().fill(lang==='ja'?'紹介文を作って':'Create a product introduction')
    await page.getByRole('button',{name:start,exact:true}).click()
    await page.waitForURL(/\/runs\//)
    await page.locator('.work-chat-first').waitFor()
    await page.waitForTimeout(2000)
    const grid=await page.locator('.work-chat-first').evaluate(el=>getComputedStyle(el).gridTemplateColumns)
    const checkedTabs=[]
    for(const name of lang==='ja'?['チームチャット','時系列','最終報告','承認']:['Team chat','Timeline','Final report','Approvals']){
      const button=page.locator('.chat-main .tabs button').filter({hasText:name})
      if(await button.count()!==1)throw new Error(`Expected exactly one required tab: ${name}`)
      await button.click()
      if(!(await button.getAttribute('class'))?.split(/\s+/).includes('active'))throw new Error(name+' did not activate')
      if(await page.evaluate('document.documentElement.scrollWidth>innerWidth+1'))throw new Error(name+' overflows')
      checkedTabs.push(name)
    }
    const artifact=await page.locator('.chat-side>.pane').last().boundingBox()
    if(width===1440 && (!artifact||artifact.width<650))throw new Error('Artifact reading surface is too narrow')
    await page.screenshot({path:`${shots}/run-${lang}-${width}.png`,fullPage:true})
    await page.goto(base+'/settings',{waitUntil:'networkidle'})
    if(await page.evaluate('document.documentElement.scrollWidth>innerWidth+1'))throw new Error('Settings overflows')
    if(errors.length)throw new Error(errors.join('\n'))
    report.push({width,lang,grid,artifactWidth:artifact?.width,checkedTabs,settings:true,provider:'scripted test backend'})
    await context.close()
  }
}finally{await browser.close();writeFileSync(shots+'/report.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report))}

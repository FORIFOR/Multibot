// Exercise the real browser's sessionStorage quota using only actual repository evidence.
import assert from 'node:assert/strict'
import { chromium } from 'playwright-core'
import { readFileSync, readdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
const base=process.env.QUALITY_BASE || 'http://127.0.0.1:8796',out=resolve('../artifacts/product-quality')
assert.ok(['127.0.0.1','localhost'].includes(new URL(base).hostname))
const files=readdirSync(resolve('../docs/evidence'),{recursive:true}).filter(p=>p.endsWith('.jsonl'))
const documents=files.map(p=>({name:p,text:readFileSync(resolve('../docs/evidence',p),'utf8')}))
const browser=await chromium.launch({channel:'chrome',headless:true})
try{
 const page=await browser.newPage({locale:'ja-JP'});await page.goto(base);await page.locator('#request-goal').waitFor()
 await page.locator('#request-goal').fill(readFileSync(resolve('../docs/design/brief.md'),'utf8'))
 await page.waitForFunction(()=>sessionStorage.getItem('agentteam.requestDraft')?.includes('デザインブリーフ'))
 const quota=await page.evaluate(documents=>{let count=0;try{for(const d of documents){sessionStorage.setItem('quality-evidence:'+d.name,d.text);count++}}catch(e){return{count,error:e.name}}return{count,error:null}},documents)
 assert.equal(quota.error,'QuotaExceededError')
 await page.evaluate(lines=>{for(const [i,line] of lines.entries()){try{sessionStorage.setItem('quality-evidence-line:'+i,line)}catch{ /* Real quota remains exhausted. */ }}},documents.flatMap(d=>d.text.split('\n')).slice(0,5000))
 const actual=readFileSync(resolve('../docs/quality/integration.md'),'utf8')
 await page.locator('#request-goal').fill(actual)
 await page.getByText('ブラウザーに保存できません。',{exact:false}).waitFor()
 await page.getByRole('link',{name:/マイチーム/}).first().click();await page.goBack()
 assert.equal(await page.locator('#request-goal').inputValue(),actual)
 writeFileSync(`${out}/draft-quota.json`,JSON.stringify({status:'PASS',quota,preserved:'docs/quality/integration.md',bytes:Buffer.byteLength(actual),browser:browser.version()},null,2))
 console.log('PASS: quota exceeded with real evidence; latest draft survives settings navigation')
}finally{await browser.close()}

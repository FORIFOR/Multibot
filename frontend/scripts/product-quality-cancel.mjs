// Cancel the real start:false request created by the accepted-idempotency check.
import assert from 'node:assert/strict'
import { chromium } from 'playwright-core'
import { readFileSync,writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
const out=resolve('../artifacts/product-quality'),saved=JSON.parse(readFileSync(`${out}/accepted-idempotency.json`,'utf8'))
const base='http://127.0.0.1:8796',browser=await chromium.launch({channel:'chrome',headless:true})
try{
 const context=await browser.newContext({locale:'ja-JP'}),page=await context.newPage()
 const before=await(await context.request.get(`${base}/api/runs/${saved.run_id}`)).json()
 assert.equal(before.status,'created');assert.equal(before.usage.model_calls,0)
 await page.goto(`${base}/runs/${saved.run_id}`)
 await page.getByRole('button',{name:'作業を止める'}).focus();await page.keyboard.press('Enter')
 await page.getByText('再開できる計画がありません。',{exact:false}).waitFor()
 assert.equal(await page.getByRole('button',{name:'続きを進める'}).count(),0)
 const after=await(await context.request.get(`${base}/api/runs/${saved.run_id}`)).json()
 assert.equal(after.status,'cancelled');assert.equal(after.usage.model_calls,0)
 writeFileSync(`${out}/cancel.json`,JSON.stringify({status:'PASS',run_id:saved.run_id,before:before.status,after:after.status,model_calls:0,no_invalid_resume_button:true},null,2))
 await page.screenshot({path:`${out}/cancelled-no-plan.png`,fullPage:true})
 console.log('PASS: explicit keyboard cancellation persists; no resume action offered without a plan')
}finally{await browser.close()}

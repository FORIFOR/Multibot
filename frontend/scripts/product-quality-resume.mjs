// Explicit recovery of the real interrupted loopback run after inspecting its effects.
import assert from 'node:assert/strict'
import { chromium } from 'playwright-core'
import { readFileSync,writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
const base='http://127.0.0.1:8796',out=resolve('../artifacts/product-quality'),id=readFileSync(`${out}/run-id.txt`,'utf8').trim()
const browser=await chromium.launch({channel:'chrome',headless:true})
try{
 const context=await browser.newContext({viewport:{width:1440,height:1000},locale:'ja-JP',reducedMotion:'reduce'})
 const before=await(await context.request.get(`${base}/api/runs/${id}`)).json()
 assert.equal(before.status,'interrupted');assert.equal(before.usage.tool_calls,0);assert.ok(before.plan)
 writeFileSync(`${out}/interrupted-run.json`,JSON.stringify(before,null,2))
 const page=await context.newPage();await page.goto(`${base}/runs/${id}`)
 const button=page.getByRole('button',{name:'続きを進める'});await button.waitFor()
 await page.screenshot({path:`${out}/workroom-interrupted.png`,fullPage:true})
 await button.focus();await page.keyboard.press('Enter')
 await page.waitForFunction(()=>!document.querySelector('.status-voice')?.textContent.includes('中断'))
 const after=await(await context.request.get(`${base}/api/runs/${id}`)).json()
 assert.equal(after.run_id,before.run_id);assert.equal(after.status,'running')
 writeFileSync(`${out}/resume.json`,JSON.stringify({before:before.status,after:after.status,run_id:id,inspected_tool_calls:before.usage.tool_calls,explicit_keyboard_action:true},null,2))
 console.log('PASS: explicit keyboard resume of the same real run after inspecting zero tool effects')
}finally{await browser.close()}

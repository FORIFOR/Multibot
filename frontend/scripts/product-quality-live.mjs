// Real loopback service/browser verification. No fake provider, route fulfillment or fabricated record.
import assert from 'node:assert/strict'
import { chromium } from 'playwright-core'
import { mkdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
const base=process.env.QUALITY_BASE || 'http://127.0.0.1:8796'
assert.ok(['127.0.0.1','localhost'].includes(new URL(base).hostname),'verification requires loopback')
const out=resolve('../artifacts/product-quality'); mkdirSync(out,{recursive:true})
const browser=await chromium.launch({channel:'chrome',headless:true})
const context=await browser.newContext({viewport:{width:1440,height:1000},locale:'ja-JP',reducedMotion:'reduce',acceptDownloads:true})
const page=await context.newPage(), errors=[], observations=[]
page.on('pageerror',e=>errors.push(e.message))
const note=(name,detail)=>{observations.push({name,detail});writeFileSync(`${out}/browser-start.json`,JSON.stringify({browser:browser.version(),errors,observations},null,2));console.log(name)}
try {
 await page.goto(base); await page.locator('#request-goal').waitFor()
 await page.waitForFunction(()=>document.querySelector('.request-disclosure')?.textContent.includes('127.0.0.1:11434'))
 await page.locator('.request-examples button').first().focus(); await page.keyboard.press('Enter')
 assert.match(await page.locator('#request-goal').inputValue(),/guide.md/)
 assert.equal(await page.locator('#request-goal').evaluate(e=>e===document.activeElement),true)
 const request='添付した integration.md だけを根拠に、初めてAgent Teamを組み込む開発者向けの短い日本語導入ガイド guide.md を作ってください。見出しは「前提条件」「最初の手順」「制約・未確認」の3つ。合計400〜700字程度。HTTPの202は完了ではないこと、採用した版のZIP保存、応答喪失時の再送の注意を必ず含め、根拠の節名を示してください。外部検索や外部送信は行わず、資料にない動作を断言しないでください。';
 await page.locator('#request-goal').fill(request)
 await page.locator('details.more > summary').first().click()
 await page.locator('#run-attachments').setInputFiles(resolve('../docs/quality/integration.md'))
 await page.getByRole('link',{name:/マイチーム|My team/}).first().click()
 await page.goBack();await page.locator('#request-goal').waitFor()
 assert.equal(await page.locator('#request-goal').inputValue(),request)
 await page.reload();await page.locator('#request-goal').waitFor();assert.equal(await page.locator('#request-goal').inputValue(),request)
 await page.locator('details.more > summary').first().click();assert.equal(await page.locator('.attachment-item').count(),1)
 note('draft navigation and reload', 'actual integration.md attachment and Japanese request retained')
 // Chromium IME composition events; does not substitute for an OS Japanese input-method test.
 const cdp=await context.newCDPSession(page);await page.locator('#request-goal').focus()
 await cdp.send('Input.imeSetComposition',{text:'確認',selectionStart:2,selectionEnd:2})
 await cdp.send('Input.insertText',{text:'確認'});await page.locator('#request-goal').fill(request)
 note('browser composition','Chromium composition/commit completed; real OS IME remains BLOCKED')
 await page.screenshot({path:`${out}/home-desktop.png`,fullPage:true})
 let mutations=0;page.on('request',r=>{if(r.method()==='POST'&&new URL(r.url()).pathname==='/api/runs')mutations++})
 await context.setOffline(true);await page.locator('.ask button[type=submit]').click();await page.locator('.ask [role=alert]').waitFor()
 assert.equal(mutations,1,'failed mutation must not be automatically retried')
 assert.equal(await page.locator('#request-goal').inputValue(),request)
 await context.setOffline(false);note('offline recovery','one attempted POST; no automatic retry; draft preserved')
 // Explicit user retry through the same button; all configured model calls stay loopback.
 await page.locator('.ask button[type=submit]').focus();await page.keyboard.press('Enter');await page.waitForURL(/\/runs\//)
 const runId=new URL(page.url()).pathname.split('/').pop();writeFileSync(`${out}/run-id.txt`,runId)
 await page.locator('.result-empty').waitFor();note('empty workroom',runId)
 await page.screenshot({path:`${out}/workroom-empty.png`,fullPage:true})
 // Keep the mounted component alive until the first real file arrives (Hook regression).
 await page.locator('.result-reader').waitFor({timeout:540000})
 assert.deepEqual(errors,[]);note('empty to first real artifact','no page exception')
 await page.screenshot({path:`${out}/workroom-first-artifact.png`,fullPage:true})
 writeFileSync(`${out}/first-run.json`,JSON.stringify(await (await context.request.get(`${base}/api/runs/${runId}`)).json(),null,2))
} finally {note('browser errors',errors);await browser.close()}

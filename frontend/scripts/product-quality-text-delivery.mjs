// Actual source-to-file task, loopback model only. No response injection.
import { chromium } from 'playwright-core'
import assert from 'node:assert/strict'
import { mkdirSync,writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
const out=resolve(process.env.QUALITY_OUT || '../artifacts/product-quality/text-delivery-1')
mkdirSync(out,{recursive:true})
const browser=await chromium.launch({channel:'chrome',headless:true})
try {
 const context=await browser.newContext({viewport:{width:1440,height:1000},locale:'ja-JP',reducedMotion:'reduce'})
 const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message))
 await page.goto('http://127.0.0.1:8796')
 await page.locator('#request-goal').fill('添付した integration.md だけを根拠に、初めてAgent Teamを組み込む開発者向けの短い日本語導入ガイド guide.md を作ってください。見出しは「前提条件」「最初の手順」「制約・未確認」の3つ。合計400〜700字。HTTP 202は完了ではないこと、採用した版のZIP保存、応答喪失時の再送の注意を必ず含め、根拠の節名を示してください。新しいキーを使える条件や省略時の挙動を変えて説明しないでください。外部検索や外部送信は行わず、資料にない動作を断言しないでください。確認担当は本文と原資料を照合し、実測した文字数で検証してください。')
 await page.locator('details.more').first().locator('summary').click()
 await page.locator('#run-attachments').setInputFiles(resolve('../docs/quality/integration.md'))
 await page.getByText('成果物の条件を指定する（任意）',{exact:true}).click()
 await page.getByLabel('成果物のファイル名',{exact:true}).fill('guide.md')
 await page.getByLabel('最小文字数',{exact:true}).fill('400')
 await page.getByLabel('最大文字数',{exact:true}).fill('700')
 if (process.env.QUALITY_DOCUMENT === '1') await page.getByLabel('添えた資料から1つの文書を作る',{exact:true}).check()
 await page.reload();await page.getByText('成果物の条件を指定する（任意）',{exact:true}).click()
 assert.equal(await page.getByLabel('最小文字数',{exact:true}).inputValue(),'400')
 assert.equal(await page.getByLabel('最大文字数',{exact:true}).inputValue(),'700')
 await page.screenshot({path:`${out}/request.png`,fullPage:true})
 await page.getByRole('button',{name:'チームにお願いする',exact:true}).click()
 await page.waitForURL(/\/runs\//)
 const id=page.url().split('/').pop();writeFileSync(`${out}/run-id.txt`,id)
 const initial=await(await context.request.get(`http://127.0.0.1:8796/api/runs/${id}`)).json()
 if (process.env.QUALITY_DOCUMENT === '1') assert.equal(initial.inputs.workflow,'document')
 assert.equal(initial.inputs.delivery_requirements[0].input_format,'text')
 assert.equal(initial.inputs.delivery_requirements[0].json_schema.maxLength,700)
 writeFileSync(`${out}/initial.json`,JSON.stringify(initial,null,2));console.log('RUN '+id)
 await page.locator('.result-reader').waitFor({timeout:510000})
 assert.deepEqual(errors,[])
 await page.screenshot({path:`${out}/first-result.png`,fullPage:true})
 writeFileSync(`${out}/browser.json`,JSON.stringify({errors,browser:browser.version(),empty_to_first_artifact:'PASS'},null,2))
 console.log('PASS mounted first artifact')
}finally{await browser.close()}

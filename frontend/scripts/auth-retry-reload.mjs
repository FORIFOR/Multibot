/** Real API response loss via Chrome CDP, no mocked response and no LLM execution.
 * Uses the real production bundle API with the server's supported start:false request flag.
 * Explicit loopback URL, private admin key file, isolated data directory and output path required.
 */
import { chromium } from 'playwright-core'
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { execFileSync } from 'node:child_process'
import assert from 'node:assert/strict'
const origin=process.env.AUTH_TEST_URL, keyFile=process.env.AUTH_TEST_ADMIN_KEY_FILE, data=process.env.AUTH_TEST_DATA_DIR, out=process.env.AUTH_TEST_EVIDENCE_DIR
assert.ok(origin&&keyFile&&data&&out)
assert.ok(['127.0.0.1','localhost'].includes(new URL(origin).hostname))
const source=readFileSync(new URL('../../docs/PRODUCTION_PLAN.md',import.meta.url),'utf8')
const input={goal:source.split('\n').find(s=>s.startsWith('Goal:')),inputs:{text:source,urls:[],files:[]},start:false}
const sql=q=>JSON.parse(execFileSync('sqlite3',['-json',resolve(data,'agentteam.sqlite'),q],{encoding:'utf8'})||'[]')
const before=sql('SELECT count(*) AS count FROM runs;')[0].count
const browser=await chromium.launch({channel:'chrome'}), context=await browser.newContext({locale:'ja-JP'}), page=await context.newPage()
mkdirSync(out,{recursive:true})
try {
  await page.goto(origin)
  await page.locator('#access-key').fill(readFileSync(keyFile,'utf8').trim())
  await page.getByRole('button',{name:'ログイン',exact:true}).click()
  await page.locator('#request-goal').waitFor()
  const send=()=>page.evaluate(async body=>{
    const bundle=await import(document.querySelector('script[type="module"]').src)
    const api=Object.values(bundle).find(v=>v&&typeof v==='object'&&typeof v.createRun==='function')
    if(!api) throw new Error('Production API export not found')
    try {return {ok:true,run:await api.createRun(body)}}catch(error){return{ok:false,status:error.status,body:error.body,name:error.name}}
  },input)
  const client=await context.newCDPSession(page)
  const actual=[]
  await client.send('Fetch.enable',{patterns:[{urlPattern:'*/api/runs',requestStage:'Response'}]})
  client.on('Fetch.requestPaused',async event=>{
    if(event.request.method==='POST'){
      actual.push({status:event.responseStatusCode,key:event.request.headers['Idempotency-Key']})
      await client.send('Fetch.failRequest',{requestId:event.requestId,errorReason:'ConnectionReset'})
    }else await client.send('Fetch.continueRequest',{requestId:event.requestId})
  })
  const lost=await send()
  assert.equal(lost.ok,false)
  const stored=await page.evaluate(()=>sessionStorage.getItem('agentteam.pendingCommands'))
  const entry=JSON.parse(stored)['POST /api/runs']
  assert.ok(/^[a-f0-9]{64}$/.test(entry.signature))
  assert.deepEqual(Object.keys(entry).sort(),['key','signature'])
  assert.equal(sql('SELECT count(*) AS count FROM runs;')[0].count,before+1)
  assert.equal(sql('SELECT count(*) AS count FROM execution_jobs;')[0].count,0)
  await client.send('Fetch.disable')
  await page.reload()
  await page.locator('#request-goal').waitFor()
  assert.equal(JSON.parse(await page.evaluate(()=>sessionStorage.getItem('agentteam.pendingCommands')))['POST /api/runs'].key,entry.key)
  const headers=[]
  page.on('request',request=>{if(request.method()==='POST'&&new URL(request.url()).pathname==='/api/runs')headers.push(request.headers()['idempotency-key'])})
  const retried=await send()
  assert.equal(headers[0],entry.key)
  assert.equal(sql('SELECT count(*) AS count FROM runs;')[0].count,before+1,'The server must replay the prior receipt instead of creating another run.')
  assert.equal(await page.evaluate(()=>sessionStorage.getItem('agentteam.pendingCommands')),null)
  // Once a result has actually arrived, a deliberate identical new request gets a new key.
  await send()
  assert.notEqual(headers[1],headers[0])
  assert.equal(sql('SELECT count(*) AS count FROM runs;')[0].count,before+2)
  assert.equal(sql('SELECT count(*) AS count FROM execution_jobs;')[0].count,0)
  const result={checked_at:new Date().toISOString(),browser:browser.version(),status:'PASS',method:'Chrome response-stage TCP reset after real API response; same built api.ts; start:false',lost_response_http_status:actual[0]?.status,retry_http_status:retried.status||202,duplicate_run_count:0,deliberate_new_run_count:1,execution_jobs:0,stored_fields:['signature','key'],limits:['409 configuration-blocked receipts are valid delivery receipts; this is not an LLM success or business acceptance','Changed request content after unknown outcome still requires manual outcome review','Storage disabled/unreadable fails before sending rather than silently creating a fresh key']}
  writeFileSync(resolve(out,'retry-reload.json'),JSON.stringify(result,null,2)+'\n')
  console.log(JSON.stringify(result))
}finally{await browser.close()}

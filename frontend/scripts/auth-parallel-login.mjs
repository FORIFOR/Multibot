/** Real simultaneous browser sign-ins and actual shared-cookie replacement. No mocked response/model. */
import { chromium } from 'playwright-core'
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { execFileSync } from 'node:child_process'
import assert from 'node:assert/strict'
const origin=process.env.AUTH_TEST_URL, admin=process.env.AUTH_TEST_ADMIN_KEY_FILE, operator=process.env.AUTH_TEST_OPERATOR_KEY_FILE, data=process.env.AUTH_TEST_DATA_DIR, out=process.env.AUTH_TEST_EVIDENCE_DIR
assert.ok(origin&&admin&&operator&&data&&out)
assert.ok(['localhost','127.0.0.1'].includes(new URL(origin).hostname))
const key=file=>readFileSync(file,'utf8').trim()
const sql=q=>JSON.parse(execFileSync('sqlite3',['-json',resolve(data,'agentteam.sqlite'),q],{encoding:'utf8'}))[0]
const initial=sql('SELECT count(*) AS n FROM runs;').n
const source=readFileSync(new URL('../../docs/PRODUCTION_PLAN.md',import.meta.url),'utf8')
const browser=await chromium.launch({channel:'chrome'}), context=await browser.newContext({locale:'ja-JP'}), a=await context.newPage(), b=await context.newPage(), checks=[]
mkdirSync(out,{recursive:true})
try {
  for(const [page,file] of [[a,admin],[b,operator]]) {await page.goto(origin); await page.locator('#access-key').fill(key(file))}
  const clients=await Promise.all([a,b].map(p=>context.newCDPSession(p))), held=[]
  for(let i=0;i<clients.length;i++){
    await clients[i].send('Fetch.enable',{patterns:[{urlPattern:'*/api/auth/login',requestStage:'Response'}]})
    clients[i].on('Fetch.requestPaused',event=>held.push({client:clients[i],event}))
  }
  for (const interruptSecond of [false, true]) {
    if (interruptSecond) {
      await context.clearCookies()
      for (const [page, file] of [[a, admin], [b, operator]]) { await page.reload(); await page.locator('#access-key').fill(key(file)) }
      held.length = 0
    }
    // Both actual forms are submitted together before the cross-tab notifications can close them.
    const at=Date.now()+200
    await Promise.all([a,b].map(p=>p.evaluate(async at=>{await new Promise(r=>setTimeout(r,Math.max(0,at-Date.now())));document.querySelector('form').requestSubmit()},at)))
    const deadline=Date.now()+5000
    while(held.length<2&&Date.now()<deadline) await new Promise(r=>setTimeout(r,20))
    assert.equal(held.length,2,'Both real login requests must reach the server to exercise the race.')
    assert.ok(held.every(x=>x.event.responseStatusCode===200))
    await held[0].client.send('Fetch.continueRequest',{requestId:held[0].event.requestId})
    await new Promise(r=>setTimeout(r,100))
    assert.equal(await a.locator('#request-goal').count()+await b.locator('#request-goal').count(),0)
    if(interruptSecond) await held[1].client.send('Fetch.failRequest',{requestId:held[1].event.requestId,errorReason:'ConnectionReset'})
    else await held[1].client.send('Fetch.continueRequest',{requestId:held[1].event.requestId})
    for(const page of[a,b]) {await page.locator('#access-key').waitFor();assert.equal(await page.locator('#request-goal').count(),0)}
    checks.push({id:interruptSecond?'parallel-signin-response-loss':'parallel-real-signin',status:'PASS',observed:interruptSecond?'Second real HTTP 200 response interrupted at response stage; stale catch closes both workspaces and permits re-login.':'Two real HTTP 200 login responses released in sequence; both old workspaces stay closed and re-login remains available.'})
  }
  for(const client of clients) await client.send('Fetch.disable')
  await b.close()
  await a.locator('#access-key').fill(key(admin));await a.getByRole('button',{name:'ログイン',exact:true}).click();await a.locator('#request-goal').waitFor()
  await a.locator('#request-goal').fill(source.split('\n').find(s=>s.startsWith('Goal:')))
  const before=await a.evaluate(async()=>(await(await fetch('/api/auth/me')).json()).subject)
  // Real key login replaces the shared cookie without frontend notifications, exposing the smallest race window.
  const response=await context.request.post(origin+'/api/auth/login',{data:{token:key(operator)},headers:{Origin:origin}})
  assert.equal(response.status(),200)
  const after=(await response.json()).subject
  assert.notEqual(before,after)
  const seen=[];a.on('request',r=>{if(new URL(r.url()).pathname==='/api/runs'&&r.method()==='POST') seen.push(r.headers()['x-agentteam-subject'])})
  const result=await a.evaluate(async source=>{const bundle=await import(document.querySelector('script[type="module"]').src);const api=Object.values(bundle).find(x=>x&&typeof x==='object'&&typeof x.createRun==='function');try{await api.createRun({goal:source.split('\n').find(s=>s.startsWith('Goal:')),inputs:{text:source,urls:[],files:[]},start:false});return{status:202}}catch(error){return{status:error.status}}},source)
  assert.equal(seen[0],before)
  assert.equal(result.status,401)
  await a.locator('#access-key').waitFor()
  assert.equal(sql('SELECT count(*) AS n FROM runs;').n,initial)
  checks.push({id:'cookie-subject-mismatch',status:'PASS',observed:'The real cookie changes while the old request draft is open; its mutation carries the bound prior subject and receives HTTP 401 before any run is created.'})
  assert.equal(sql('SELECT count(*) AS n FROM execution_jobs;').n,0)
  const resultDoc={checked_at:new Date().toISOString(),browser:browser.version(),checks,additional_runs:0,execution_jobs:0,limits:['Local real keys, not an external IdP acceptance test','Response ordering is controlled by CDP without supplying any response bytes']}
  writeFileSync(resolve(out,'parallel-login.json'),JSON.stringify(resultDoc,null,2)+'\n');console.log(JSON.stringify(resultDoc))
}catch(error){const suffix=Date.now();writeFileSync(resolve(out,`parallel-failure-${suffix}.json`),JSON.stringify({checks,error:String(error)},null,2));await a.screenshot({path:resolve(out,`parallel-failure-${suffix}.png`)});throw error}finally{await browser.close()}

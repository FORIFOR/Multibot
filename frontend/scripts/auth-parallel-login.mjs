/** Real sign-ins synchronized at submit tasks, plus shared-cookie replacement. No fabricated responses. */
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
let browser, context, a, b
let clients=[]
const debugState=[{paused:false},{paused:false}]
const checks=[]
mkdirSync(out,{recursive:true})
const diagnostic={status:'RUNNING',phase:'browser_launch',error_name:null,passed_check_ids:[],rounds:[],debug_cleanup:[],scheduling:"Real DOMDebugger submit breakpoint barrier; not natural simultaneous-user timing"}
let activeRound
const saveDiagnostic=()=>{diagnostic.passed_check_ids=checks.filter(check=>check.status==='PASS').map(check=>check.id);writeFileSync(resolve(out,'parallel-diagnostic.json'),JSON.stringify(diagnostic,null,2)+'\n')}
const bounded=async(label,operation,ms)=>{let timer;try{return await Promise.race([operation(),new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error(label)),ms)})])}finally{clearTimeout(timer)}}
const releaseDebuggers=async()=>{
 for(let index=0;index<clients.length;index++){
  const page=[a,b][index],client=clients[index],row={page:index===0?'A':'B',target_closed:page.isClosed(),steps:[]}
  diagnostic.debug_cleanup.push(row)
  if(row.target_closed)continue
  for(const [name,method,args]of [['remove_breakpoint','DOMDebugger.removeEventListenerBreakpoint',{eventName:'submit'}],...(debugState[index].paused?[['resume','Debugger.resume',{}]]:[]),['disable_debugger','Debugger.disable',{}],['disable_fetch','Fetch.disable',{}]]){
   try{await bounded(name,()=>client.send(method,args),3000);row.steps.push({name,status:'PASS'})}
   catch(error){row.steps.push({name,status:'FAIL',error_name:safeErrorName(error)});diagnostic.status='FAIL'}
  }
 }
 saveDiagnostic()
}
const collectObservations=async()=>{
  if(!activeRound)return
  activeRound.pages=await Promise.all([a,b].map(async(page,index)=>{
    let timer
    try{
      const probe=await Promise.race([page.evaluate(()=>{const probe=window.__parallelSigninProbe;return probe?{events:probe.events,dropped_events:probe.dropped}:null}),new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error('observation deadline')),2000)})])
      return{page:index===0?'A':'B',page_closed:page.isClosed(),probe}
    }catch(error){return{page:index===0?'A':'B',page_closed:page.isClosed(),observation_error_name:safeErrorName(error)}}
    finally{clearTimeout(timer)}
  }))
}
const safeErrorName=error=>['Error','AssertionError','TimeoutError','TypeError','ProtocolError','TargetClosedError'].includes(error?.name)?error.name:'Error'
try {
  browser=await chromium.launch({channel:'chrome'});context=await browser.newContext({locale:'ja-JP'});a=await context.newPage();b=await context.newPage()
  diagnostic.phase='initial_login_forms'
  for(const [page,file] of [[a,admin],[b,operator]]) {await page.goto(origin); await page.locator('#access-key').fill(key(file))}
  diagnostic.phase='response_observation_setup'
  clients=await Promise.all([a,b].map(p=>context.newCDPSession(p))); const held=[]
  for(let i=0;i<clients.length;i++){
    await clients[i].send('Fetch.enable',{patterns:[{urlPattern:'*/api/auth/login',requestStage:'Response'}]})
    await clients[i].send('Debugger.enable')
    clients[i].on('Debugger.paused',event=>{
      debugState[i].paused=true
      if(activeRound?.barrier)activeRound.barrier.pauses.push({page:i===0?'A':'B',epoch_ms:Date.now(),reason:event.reason==='EventListener'?'EventListener':'other',actual_submit_event:event.data?.eventName==='listener:submit'||event.data?.eventName==='submit'})
    })
    clients[i].on('Debugger.resumed',()=>{debugState[i].paused=false})
    clients[i].on('Fetch.requestPaused',event=>{held.push({client:clients[i],event});activeRound?.held_responses.push({page:i===0?'A':'B',epoch_ms:Date.now(),status:event.responseStatusCode??null})})
    ;[a,b][i].on('request',request=>{if(request.method()==='POST'&&new URL(request.url()).pathname==='/api/auth/login')activeRound?.login_requests.push({page:i===0?'A':'B',epoch_ms:Date.now()})})
  }
  for (const interruptSecond of [false, true]) {
    const phase=stage=>{diagnostic.phase=(interruptSecond?'response_loss_':'parallel_')+stage}
    if (interruptSecond) {
      phase('reset_login_forms')
      await context.clearCookies()
      for (const [page, file] of [[a, admin], [b, operator]]) { await page.reload(); await page.locator('#access-key').fill(key(file)) }
      held.length = 0
    }
    activeRound={id:interruptSecond?'response_loss':'parallel',pages:[],submission_settled:[],login_requests:[],held_responses:[]}
    diagnostic.rounds.push(activeRound)
    // Observe genuine events without delaying handlers, changing notifications or retaining credentials.
    await Promise.all([a,b].map(page=>page.evaluate(()=>{
      const probe={events:[],dropped:0}
      const record=kind=>{
        const input=document.querySelector('#access-key'),form=document.querySelector('form'),button=form?.querySelector('button')
        const row={kind,epoch_ms:Date.now(),performance_ms:performance.now(),form_count:document.querySelectorAll('form').length,input_present:!!input,input_has_value:!!input?.value,input_valid:input?input.validity.valid:null,submit_disabled:button?button.disabled:null,connecting_count:document.querySelectorAll('main[role="status"]').length,workspace_count:document.querySelectorAll('#request-goal').length}
        if(probe.events.length<64)probe.events.push(row);else probe.dropped++
        return row
      }
      const peer=(kind,value)=>{const row=record(kind);row.pending=value?.pending===true}
      document.addEventListener('submit',()=>record('actual_submit_event'),true)
      const channel=new BroadcastChannel('agentteam.sessionChange')
      channel.onmessage=event=>peer('broadcast_received',event.data)
      window.addEventListener('storage',event=>{if(event.key==='agentteam.sessionChange'){try{peer('storage_received',JSON.parse(event.newValue||'{}'))}catch{record('storage_parse_failed')}}})
      window.__parallelSigninProbe=Object.assign(probe,{record,channel})
      // Keep one shared array; no form values, identities or message sender IDs are recorded.
      record('probe_installed')
    })))
    // The common timer target is not an atomic barrier: a peer may close a form before its timer runs.
    phase('install_real_submit_breakpoints')
    activeRound.barrier={deadline_ms:5000,pauses:[],both_actual_submit_tasks_paused:false,release:[]}
    await Promise.all(clients.map(client=>bounded('install submit breakpoint',()=>client.send('DOMDebugger.setEventListenerBreakpoint',{eventName:'submit'}),3000)))
    phase('submit_both_forms')
    const at=Date.now()+200
    activeRound.target_epoch_ms=at
    const pendingSubmissions=Promise.allSettled([a,b].map(p=>p.evaluate(async at=>{
      window.__parallelSigninProbe.record('timer_registered')
      await new Promise(r=>setTimeout(r,Math.max(0,at-Date.now())))
      window.__parallelSigninProbe.record('timer_fired_before_request_submit')
      try{document.querySelector('form').requestSubmit();window.__parallelSigninProbe.record('request_submit_returned')}
      catch(error){window.__parallelSigninProbe.record('request_submit_threw');throw error}
    },at)))
    try{
      phase('await_both_real_submit_pauses')
      const pauseDeadline=Date.now()+activeRound.barrier.deadline_ms
      while(!(debugState.every(state=>state.paused)&&['A','B'].every(page=>activeRound.barrier.pauses.some(row=>row.page===page&&row.actual_submit_event)))&&Date.now()<pauseDeadline)await new Promise(resolve=>setTimeout(resolve,10))
      activeRound.barrier.both_actual_submit_tasks_paused=debugState.every(state=>state.paused)&&['A','B'].every(page=>activeRound.barrier.pauses.some(row=>row.page===page&&row.actual_submit_event))
      saveDiagnostic()
      assert.ok(activeRound.barrier.both_actual_submit_tasks_paused,'Both genuine submit tasks must reach their breakpoints before either is released.')
      assert.equal(activeRound.login_requests.length,0,'The actual login handlers must not have sent requests before both submit tasks arrive.')
    }finally{
      // Remove before resume so React capture/bubble listeners cannot pause a second time.
      const removed=await Promise.allSettled(clients.map(client=>bounded('remove submit breakpoint',()=>client.send('DOMDebugger.removeEventListenerBreakpoint',{eventName:'submit'}),3000)))
      activeRound.barrier.release=removed.map((row,index)=>({page:index===0?'A':'B',breakpoint_removed:row.status==='fulfilled'}))
      const resumed=await Promise.allSettled(clients.map((client,index)=>debugState[index].paused?bounded('resume submit task',()=>client.send('Debugger.resume'),3000):Promise.resolve()))
      resumed.forEach((row,index)=>{activeRound.barrier.release[index].resume_completed=row.status==='fulfilled'})
      saveDiagnostic()
      assert.ok(removed.every(row=>row.status==='fulfilled')&&resumed.every(row=>row.status==='fulfilled'),'Both owned targets must be released.')
    }
    const submitted=await bounded('submitted forms complete',()=>pendingSubmissions,5000)
    activeRound.submission_settled=submitted.map((result,index)=>({page:index===0?'A':'B',fulfilled:result.status==='fulfilled',error_name:result.status==='rejected'?safeErrorName(result.reason):null}))
    await collectObservations();saveDiagnostic()
    const rejected=submitted.find(result=>result.status==='rejected')
    if(rejected)throw rejected.reason
    const deadline=Date.now()+5000
    phase('await_both_responses')
    while(held.length<2&&Date.now()<deadline) await new Promise(r=>setTimeout(r,20))
    assert.equal(held.length,2,'Both real login requests must reach the server to exercise the race.')
    assert.ok(held.every(x=>x.event.responseStatusCode===200))
    assert.ok(['A','B'].every(page=>activeRound.held_responses.filter(row=>row.page===page&&row.status===200).length===1),'Each actual page must supply exactly one held HTTP200.')
    phase('release_first_response')
    await held[0].client.send('Fetch.continueRequest',{requestId:held[0].event.requestId})
    await new Promise(r=>setTimeout(r,100))
    phase('check_closed_workspaces')
    assert.equal(await a.locator('#request-goal').count()+await b.locator('#request-goal').count(),0)
    phase('release_second_response')
    if(interruptSecond) await held[1].client.send('Fetch.failRequest',{requestId:held[1].event.requestId,errorReason:'ConnectionReset'})
    else await held[1].client.send('Fetch.continueRequest',{requestId:held[1].event.requestId})
    phase('check_login_screens')
    for(const page of[a,b]) {await page.locator('#access-key').waitFor();assert.equal(await page.locator('#request-goal').count(),0)}
    await collectObservations()
    checks.push({id:interruptSecond?'parallel-signin-response-loss':'parallel-real-signin',status:'PASS',observed:interruptSecond?'Second real HTTP 200 response interrupted at response stage; stale catch closes both workspaces and permits re-login.':'Two real HTTP 200 login responses released in sequence; both old workspaces stay closed and re-login remains available.'})
    // Later explicit logins are outside the completed concurrency observation.
    activeRound=null
  }
  diagnostic.phase='disable_response_observation'
  for(const client of clients) await client.send('Fetch.disable')
  await b.close()
  diagnostic.phase='restore_admin_login'
  await a.locator('#access-key').fill(key(admin));await a.getByRole('button',{name:'ログイン',exact:true}).click();await a.locator('#request-goal').waitFor()
  await a.locator('#request-goal').fill(source.split('\n').find(s=>s.startsWith('Goal:')))
  const before=await a.evaluate(async()=>(await(await fetch('/api/auth/me')).json()).subject)
  // Real key login replaces the shared cookie without frontend notifications, exposing the smallest race window.
  diagnostic.phase='replace_cookie_with_operator'
  const response=await context.request.post(origin+'/api/auth/login',{data:{token:key(operator)},headers:{Origin:origin}})
  assert.equal(response.status(),200)
  const after=(await response.json()).subject
  assert.notEqual(before,after)
  const seen=[];a.on('request',r=>{if(new URL(r.url()).pathname==='/api/runs'&&r.method()==='POST') seen.push(r.headers()['x-agentteam-subject'])})
  diagnostic.phase='submit_prior_subject_request'
  const result=await a.evaluate(async source=>{const bundle=await import(document.querySelector('script[type="module"]').src);const api=Object.values(bundle).find(x=>x&&typeof x==='object'&&typeof x.createRun==='function');try{await api.createRun({goal:source.split('\n').find(s=>s.startsWith('Goal:')),inputs:{text:source,urls:[],files:[]},start:false});return{status:202}}catch(error){return{status:error.status}}},source)
  diagnostic.phase='check_subject_mismatch_rejection'
  assert.equal(seen[0],before)
  assert.equal(result.status,401)
  await a.locator('#access-key').waitFor()
  assert.equal(sql('SELECT count(*) AS n FROM runs;').n,initial)
  checks.push({id:'cookie-subject-mismatch',status:'PASS',observed:'The real cookie changes while the old request draft is open; its mutation carries the bound prior subject and receives HTTP 401 before any run is created.'})
  diagnostic.phase='check_no_execution_jobs'
  assert.equal(sql('SELECT count(*) AS n FROM execution_jobs;').n,0)
  const resultDoc={checked_at:new Date().toISOString(),browser:browser.version(),checks,additional_runs:0,execution_jobs:0,limits:['Local real keys, not an external IdP acceptance test','Both genuine submit tasks are paused and released with DOMDebugger; this is controlled scheduling, not natural simultaneous-user timing','Response ordering is controlled by CDP without supplying any response bytes','The original CI timer-phase failure remains unexplained; this run does not establish its cause']}
  writeFileSync(resolve(out,'parallel-login.json'),JSON.stringify(resultDoc,null,2)+'\n');console.log(JSON.stringify(resultDoc))
  diagnostic.status='PASS'
}catch(error){diagnostic.status='FAIL';diagnostic.error_name=safeErrorName(error);saveDiagnostic();await releaseDebuggers();await collectObservations();saveDiagnostic();const suffix=Date.now();writeFileSync(resolve(out,`parallel-failure-${suffix}.json`),JSON.stringify({checks,error:String(error)},null,2));if(a)await a.screenshot({path:resolve(out,`parallel-failure-${suffix}.png`)});throw error}
finally{
  await releaseDebuggers()
  try{if(browser)await bounded('owned browser close',()=>browser.close(),15000);if(diagnostic.status==='PASS')diagnostic.phase='completed'}
  catch(error){diagnostic.status='FAIL';diagnostic.phase='browser_cleanup';diagnostic.error_name=safeErrorName(error);throw error}
  finally{saveDiagnostic()}
}

if(diagnostic.status!=='PASS')process.exitCode=1

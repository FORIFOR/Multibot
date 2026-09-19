// Current-source browser regression. Explicit API fixtures; no live model calls or production data.
import assert from 'node:assert/strict'
import { chromium, webkit } from 'playwright-core'
import { createServer } from 'node:http'
import { existsSync, readFileSync, mkdirSync, writeFileSync } from 'node:fs'
import { resolve, extname, sep } from 'node:path'
const root=resolve('dist'), shots=resolve(process.env.SHOTS||'/tmp/three-step-shots')
mkdirSync(shots,{recursive:true})
const server=createServer((req,res)=>{const name=decodeURIComponent(new URL(req.url,'http://local').pathname),candidate=resolve(root,'.'+name),p=candidate.startsWith(root+sep)&&existsSync(candidate)&&extname(candidate)?candidate:resolve(root,'index.html');res.setHeader('Content-Type',({'.js':'text/javascript','.css':'text/css','.html':'text/html','.svg':'image/svg+xml'})[extname(p)]||'application/octet-stream');res.end(readFileSync(p))})
await new Promise(r=>server.listen(0,'127.0.0.1',r));const base=`http://127.0.0.1:${server.address().port}`
const isWebkit=process.env.BROWSER==='webkit', chromePath=process.env.CHROME_PATH||['/usr/bin/chromium','/usr/bin/google-chrome'].find(existsSync)
const browser=await(isWebkit?webkit:chromium).launch(isWebkit?{headless:true}:{headless:true,...(chromePath?{executablePath:chromePath}:{channel:'chrome'}),args:['--no-sandbox']})
const engine=isWebkit?'webkit':'chromium',results=[]
const iso='2026-09-19T03:00:00Z',sha='a'.repeat(64),usage={model_calls:3,tool_calls:2,input_tokens:200,output_tokens:100,cache_read_tokens:0,cache_write_tokens:0,cost_usd:.04,reserved_usd:0,wall_seconds:20}
function fixture(){
 const agents=['master','researcher','builder','reviewer'].map((id,i)=>({id,agent_id:id,role:id,enabled:true,display_name:['まとめ役','リサーチ狐','デザイン相棒','確認パンダ'][i],emoji:['🌱','🦊','🎨','🐼'][i],model:'fixture-model',connection_id:'fixture',driver:'ollama',system_prompt_file:'prompts/builder.md',system_prompt:'Use provided sources.',system_prompt_sha256:sha,prompt_mode:'auto_seed',skill_ids:[],skills:[],tools:[],effort:null,custom:false,system_prompt_override:null,base_url:'http://localhost',api_key_ref:null}))
 const task=(owner,status)=>({run_id:'journey',spec:{id:owner+'-task',owner,objective:owner==='researcher'?'資料を読み、要点をまとめます。':'資料の完成を待っています。',depends_on:[],output_paths:[],acceptance:[],write_scope:'work'},status,attempt:1,revision_round:0,result:null,blocked_reason:null,review:null,updated_at:iso})
 return {config:{revision:1,profile_name:'UI fixture',defaults:{connection_id:'fixture',model:'fixture-model',language:'ja',timezone:'Asia/Tokyo'},connections:[],agents,effective_agents:Object.fromEntries(agents.map(a=>[a.id,a])),limits:{budget_usd:1},pricing:{},policy:{},problems:[],skills:[]},run:{run_id:'journey',goal:'紹介資料をつくって、読みやすくまとめて',status:'running',created_at:iso,started_at:iso,finished_at:null,inputs:{text:'テスト用の資料',files:[],urls:[]},usage,plan:{goal:'test',assumptions:[],agents:agents.map(a=>a.id),tasks:[]},config_snapshot:{agents:Object.fromEntries(agents.map(a=>[a.id,a]))},parent_run_id:null,fork_from_seq:null,final_report:null,blocked_reason:null,provider_kind:'fake',tasks:[task('researcher','running'),task('builder','waiting')],artifacts:[],approvals:[],artifact_selection:{},last_seq:1,live:true,access:{can_write:true,can_override:true}},creates:0,instructions:0,decisions:[],failCreate:false,offline:false,failFile:false,checks:[],html:false,role:'admin'}
}
function file(n=1){return {run_id:'journey',artifact_id:'intro.md',revision:n,sha256:n===1?sha:'b'.repeat(64),logical_path:'紹介資料.md',media_type:'text/markdown',size:100,task_id:'builder-task',agent_id:'builder',created_at:iso,event_id:'published'+n,sources:[]}}
async function setup(context,store){await context.route('**/api/**',async route=>{
 const request=route.request(),path=new URL(request.url()).pathname,method=request.method(),reply=(data,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(data)})
 if(path==='/api/auth/status')return reply({enabled:false})
 if(path==='/api/auth/me')return reply({subject:'local',role:store.role,organization:null})
 if(path==='/api/health')return reply({ok:true,version:'fixture',live_runs:[],config_revision:1})
 if(path==='/api/config')return reply(store.config)
 if(path==='/api/approvals')return reply(store.run.approvals)
 if(path==='/api/runs'&&method==='GET')return reply([])
 if(path==='/api/runs'&&method==='POST'){store.creates++;await new Promise(r=>setTimeout(r,120));if(store.failCreate){store.failCreate=false;return reply({detail:'Fixture creation failure'},503)}store.run.goal=request.postDataJSON().goal;return reply(store.run,202)}
 if(path==='/api/runs/journey')return store.offline?reply({detail:'Offline fixture'},503):reply(store.run)
 if(path.endsWith('/instructions')){store.instructions++;await new Promise(r=>setTimeout(r,600));assert.equal(request.postDataJSON().kind,'change');return reply({instruction_id:'direction',state:'received',seq:2,event:{}},202)}
 if(path.endsWith('/cancel')){store.run.status='cancelled';return reply({cancel_requested:true})}
 if(path.endsWith('/resume')){store.run.status='running';return reply(store.run)}
 if(path.endsWith('/adopt')){const b=request.postDataJSON();store.run.artifact_selection['intro.md']={revision:b.revision,seq:3,event_id:'adopted',actor_id:'local',note:''};return reply({artifact_id:'intro.md',revision:b.revision,event:{},seq:3})}
 if(path.endsWith('/resolve')){const b=request.postDataJSON();assert.equal(b.expected_hash,'payload-hash');assert.equal(b.nonce,'nonce');store.decisions.push(b.decision);store.run.approvals=[];store.run.status='running';return reply({})}
 if(path.endsWith('/stream'))return route.fulfill({contentType:'text/event-stream',body:'event: ping\ndata: {}\n\n'})
 if(path.endsWith('/chat'))return reply([{seq:1,event_id:'real-message-fixture',from:'researcher',to:'builder',recorded_at:iso,task_id:'researcher-task',purpose:'handoff',text:'資料の要点をまとめました。出典を添えて、次の担当へ渡します。',artifact_refs:[],reply_to:null}])
 if(path.endsWith('/events')||path.endsWith('/timeline'))return reply([])
 if(path.startsWith('/api/artifacts/')){if(store.failFile){store.failFile=false;return reply({detail:'Fixture file failure'},503)}const rev=Number(path.match(/versions\/(\d+)/)?.[1]||1);return reply({...file(rev),text:rev===1?'はじめての方への紹介資料\n\n必要なことを、ひとつずつ。\nチームでつくり、確かめながら進めます。':'新しい版の紹介資料',checks:store.checks,reviews:[]})}
 throw new Error('Unexpected fixture endpoint '+method+' '+path)
})}
async function noOverflow(page){const d=await page.evaluate(()=>({viewport:innerWidth,width:document.documentElement.scrollWidth}));assert.ok(d.width<=d.viewport+1,JSON.stringify(d))}
const machinery=/model calls|tool calls|sha256|tokens|system_prompt|local-first|\brevision\b/
try{
 for(const[width,lang]of [[1440,'ja'],[390,'ja'],[320,'ja'],[768,'en']]){
  const context=await browser.newContext({viewport:{width,height:1000},locale:lang==='ja'?'ja-JP':'en-US',reducedMotion:'reduce',...(width<500?{isMobile:true,hasTouch:true}: {})}),store=fixture();await setup(context,store)
  const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message))
  await page.goto(base);await page.locator('#request-goal').waitFor();await noOverflow(page)
  assert.equal(await page.locator('.ask textarea:visible').count(),1)
  assert.doesNotMatch(await page.locator('body').innerText(),machinery)
  await page.locator('.request-examples button').first().click();assert.ok((await page.locator('#request-goal').inputValue()).length)
  await page.screenshot({path:`${shots}/three-step-home-${width}-${lang}-${engine}.png`,fullPage:true})
  if(width===1440){store.failCreate=true;await page.locator('.ask button[type=submit]').click();await page.locator('.ask [role=alert]').waitFor();assert.ok((await page.locator('#request-goal').inputValue()).length)}
  const before=store.creates;await page.locator('.ask').evaluate(f=>{f.requestSubmit();f.requestSubmit()});await page.waitForURL(/\/runs\/journey/);assert.equal(store.creates,before+1)
  await page.locator('.simple-bot').first().waitFor();assert.equal(await page.locator('.journey [aria-pressed=true]').getAttribute('data-journey'),'team')
  assert.doesNotMatch(await page.locator('body').innerText(),machinery)
  await page.locator('#team-direction').fill('もっと短く、分かりやすく。')
  await page.locator('[data-journey=results]').click();await page.locator('.result-empty').waitFor()
  await page.locator('[data-journey=request]').click();await page.locator('.simple-request').waitFor()
  await page.locator('[data-journey=team]').click();assert.equal(await page.locator('#team-direction').inputValue(),'もっと短く、分かりやすく。')
  await page.locator('.simple-direction button[type=submit]').click();await page.locator('[data-journey=results]').click();await page.locator('[data-journey=team]').click();await page.waitForFunction(()=>document.querySelector('#team-direction')?.value==='');assert.equal(store.instructions,1)
  await noOverflow(page);await page.screenshot({path:`${shots}/three-step-team-${width}-${lang}-${engine}.png`,fullPage:true})
  // Direct completed link defaults to results; a completion status is not a verification badge.
  store.run.status='completed';store.run.artifacts=[file()];await page.goto(base+'/runs/journey')
  await page.locator('.result-reader pre').waitFor();assert.equal(await page.locator('.journey [aria-pressed=true]').getAttribute('data-journey'),'results')
  assert.match(await page.locator('.result-review-summary').innerText(),lang==='ja'?/確認記録はまだありません/:/No check record/)
  assert.doesNotMatch(await page.locator('body').innerText(),machinery)
  await noOverflow(page);const box=await page.locator('.result-reader').boundingBox();if(width===1440)assert.ok(box.width>=650)
  await page.screenshot({path:`${shots}/three-step-results-${width}-${lang}-${engine}.png`,fullPage:true})
  await page.locator('.result-use button').click();await page.waitForFunction(()=>document.querySelector('.result-review-summary')?.textContent.match(/あなたが選んだ版|Your selected version/))
  // Retrying a failed file read must issue a new read even without a new run event.
  store.failFile=true;await page.reload();await page.locator('.simple-deliverables [role=alert]').waitFor();
  await page.locator('.simple-deliverables [role=alert] button').click();await page.waitForFunction(()=>document.querySelector('.result-reader pre')?.textContent.includes('ひとつずつ'));
  // Do not copy a pass from another revision/hash.
  store.run.artifacts=[file(),file(2)];store.run.artifact_selection={};store.checks=[{event_id:'old-check',payload:{target:{artifact_id:'intro.md',revision:1,sha256:sha},result:{status:'pass'}}}]
  await page.reload();await page.locator('.result-reader pre').waitFor();assert.match(await page.locator('.result-review-summary').innerText(),lang==='ja'?/確認記録はまだありません/:/No check record/)
  store.run.status='partial';store.run.blocked_reason='出典の確認が未完了です。';await page.reload();await page.locator('.work-status.tone-attention').waitFor();assert.match(await page.locator('.simple-results .work-warning').innerText(),lang==='ja'?/完了していません/:/not complete/)
  // Approval stays visible in EVERY basic panel, and no decision is sent until clicked.
  store.run.status='approval_required';store.run.blocked_reason=null;store.run.approvals=[{approval_id:'approval',agent_id:'builder',run_id:'journey',action:'send_email',payload:{description:'テスト用の送信案を確認してください',payload:{to:'example@example.test',subject:'Preview only'}},payload_hash:'payload-hash',nonce:'nonce',expires_at:iso,status:'pending'}]
  await page.goto(base+'/runs/journey?tab=approvals');await page.locator('#simple-approvals').waitFor();assert.equal(store.decisions.length,0)
  await page.locator('[data-journey=results]').click();assert.equal(await page.locator('.approval-callout').isVisible(),true)
  await page.locator('.simple-approval .btn.ghost').click();await page.waitForFunction(()=>!document.querySelector('.approval-callout'));assert.deepEqual(store.decisions,['reject'])
  await page.goto(base+'/runs/journey?tab=timeline');await page.locator('.chat-main .tabs').waitFor();assert.equal(await page.locator('#run-inspector').getAttribute('open'),'')
  await noOverflow(page)
  // A viewer can inspect files but not adopt a version or approve actions.
  store.run.status='completed';store.run.access={can_write:false,can_override:false};await page.goto(base+'/runs/journey');await page.locator('.result-reader').waitFor();assert.equal(await page.locator('.result-use button').count(),0)
  // Foreground resync surfaces offline state rather than displaying stale work as current.
  store.offline=true;await page.evaluate(()=>window.dispatchEvent(new Event('pageshow')));await page.locator('[role=alert]').waitFor();store.offline=false
  assert.deepEqual(errors,[]);results.push({width,lang,engine,passed:true,checks:['three steps','hidden machinery','single request input','double submit','draft and in-flight send survive panel changes','file read retry','real message fixture','completed/partial/empty','revision-bound checks','approval visibility and explicit action','read-only actions','legacy deep link','foreground resync','no overflow']});await context.close()
 }
 writeFileSync(`${shots}/three-step-${engine}.json`,JSON.stringify({ok:true,boundary:'Explicit API fixtures, not real-model or real-device acceptance',results},null,2));console.log(JSON.stringify({ok:true,results}))
}catch(error){for(const c of browser.contexts())for(const p of c.pages())await p.screenshot({path:`${shots}/three-step-failure-${engine}.png`,fullPage:true}).catch(()=>{});console.error(error);process.exitCode=1}
finally{await browser.close();await new Promise(r=>server.close(r))}

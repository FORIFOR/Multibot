// Browser regression against the freshly built dist, using an explicit in-memory API fixture.
// This validates UI interactions, not model quality or the real backend (see ui-smoke/test_custom_bot_api).
import assert from 'node:assert/strict'
import { chromium, webkit } from 'playwright-core'
import { createServer } from 'node:http'
import { existsSync, readFileSync, mkdirSync, writeFileSync } from 'node:fs'
import { resolve, extname, sep } from 'node:path'

const root = resolve('dist')
assert.ok(existsSync(resolve(root, 'index.html')), 'Build the current frontend before testing')
const shots = resolve(process.env.SHOTS || '/tmp/agentteam-polish-shots')
mkdirSync(shots, { recursive: true })
const server = createServer((req, res) => {
  const name = decodeURIComponent(new URL(req.url, 'http://localhost').pathname)
  const candidate = resolve(root, '.' + name)
  const path = candidate.startsWith(root + sep) && existsSync(candidate) && extname(candidate) ? candidate : resolve(root, 'index.html')
  res.setHeader('Content-Type', ({ '.js':'text/javascript', '.css':'text/css', '.html':'text/html', '.svg':'image/svg+xml' })[extname(path)] || 'application/octet-stream')
  res.end(readFileSync(path))
})
await new Promise(r => server.listen(0, '127.0.0.1', r))
const base = `http://127.0.0.1:${server.address().port}`
const isWebkit = process.env.BROWSER === 'webkit'
const chromePath = process.env.CHROME_PATH || ['/usr/bin/chromium', '/usr/bin/google-chrome', '/opt/google/chrome/chrome'].find(existsSync)
const browser = await (isWebkit ? webkit : chromium).launch(isWebkit ? { headless:true } : { headless:true, ...(chromePath ? { executablePath:chromePath } : { channel:'chrome' }), args:['--no-sandbox'] })
const results = []
const usage = { model_calls:3, tool_calls:4, input_tokens:100, output_tokens:100, cache_read_tokens:0, cache_write_tokens:0, cost_usd:0.03, reserved_usd:0, wall_seconds:12 }
const agent = (id, role = id) => ({ id, role, enabled:true, display_name:null, emoji:null, custom:false, connection_id:'inherit', model:'inherit', system_prompt_file:`prompts/${role}.md`, prompt_mode:'auto_seed', skill_ids:[], tools:[], system_prompt_override:null, effort:null })
function fixture() {
  const agents = [agent('master'), agent('researcher'), agent('builder'), agent('reviewer')]
  const cfg = { revision:1, profile_name:'UI fixture — not a real AI run', defaults:{connection_id:'fixture', model:'fixture-model', language:'ja', timezone:'Asia/Tokyo'}, connections:[{id:'fixture', driver:'ollama', base_url:'http://localhost:11434/v1', api_key_ref:null, capability_check:'passed', capability_detail:null, refusal_fallback:false}], agents, limits:{ budget_usd:1, max_model_calls:120 }, pricing:{}, policy:{}, problems:[], skills:[], effective_agents:{} }
  const update = () => { cfg.effective_agents = Object.fromEntries(cfg.agents.map(a => [a.id, { ...a, agent_id:a.id, driver:'ollama', base_url:'http://localhost', system_prompt:a.system_prompt_override || 'Use only the provided evidence.', system_prompt_sha256:'a'.repeat(64), skills:[] }])) }
  update()
  return { cfg, update, creates:0, attempts:0, failNext:false, lastCreated:null }
}
function runData(store) {
  const task = (owner, status, n) => ({ run_id:'ui-fixture', spec:{ id:`t${n}`, owner, objective:({researcher:'資料を調べています', builder:'比較レポートを作る準備', reviewer:'完成した資料を確認'})[owner] || '計画', depends_on:[], output_paths:[], acceptance:[] }, status, attempt:1, revision_round:0, result:null, blocked_reason:null, review:null, updated_at:'2026-09-19T00:00:00Z' })
  return { run_id:'ui-fixture', status:'running', goal:'UIテスト用：新しいプロダクトの紹介資料をつくる', inputs:{text:'',urls:[],files:[]}, created_at:'2026-09-19T00:00:00Z', started_at:'2026-09-19T00:00:00Z', finished_at:null, usage, plan:{goal:'UI fixture', assumptions:[], agents:['master','researcher','builder','reviewer'], tasks:[]}, config_snapshot:{agents:store.cfg.effective_agents}, parent_run_id:null, fork_from_seq:null, final_report:null, blocked_reason:null, provider_kind:'fake', tasks:[task('researcher','running',1), task('builder','ready',2), task('reviewer','review_pending',3)], artifacts:[], approvals:[], artifact_selection:{}, last_seq:1, live:true, access:{can_write:true, can_override:true} }
}
async function setup(context, store) {
  await context.route('**/api/**', async route => {
    const url = new URL(route.request().url()), path = url.pathname, method = route.request().method()
    const reply = (data, status = 200) => route.fulfill({status, contentType:'application/json', body:JSON.stringify(data)})
    if (path === '/api/auth/status') return reply({enabled:false})
    if (path === '/api/auth/me') return reply({subject:'local', role:'admin', organization:null})
    if (path === '/api/health') return reply({ok:true, version:'UI-fixture', config_revision:store.cfg.revision, live_runs:[]})
    if (path === '/api/config') return reply(store.cfg)
    if (path === '/api/approvals' || path === '/api/runs') return reply([])
    if (path === '/api/agents' && method === 'POST') {
      store.attempts++
      await new Promise(r => setTimeout(r, 220))
      if (store.failNext) { store.failNext = false; return reply({detail:'intentional fixture failure'}, 503) }
      const body = route.request().postDataJSON()
      assert.match(body.id, /^[a-z][a-z0-9_-]{1,31}$/)
      assert.equal(body.expected_revision, store.cfg.revision)
      assert.ok(body.display_name.trim()); assert.ok(body.system_prompt.trim())
      if (store.cfg.agents.some(a => a.id === body.id)) return reply({detail:'agent id already exists'}, 409)
      const next = { ...agent(body.id, body.role), custom:true, display_name:body.display_name, emoji:body.emoji, system_prompt_override:body.system_prompt }
      store.cfg.agents.push(next); store.cfg.revision++; store.update(); store.creates++; store.lastCreated=next
      return reply({revision:store.cfg.revision, agent:next}, 201)
    }
    if (path.startsWith('/api/agents/') && method === 'PATCH') {
      const body = route.request().postDataJSON()
      assert.equal(body.expected_revision, store.cfg.revision)
      const a = store.cfg.agents.find(a => a.id === path.split('/').pop())
      Object.assign(a, body); store.cfg.revision++; store.update()
      return reply({revision:store.cfg.revision, agent:a})
    }
    if (path === '/api/runs/ui-fixture') return reply(runData(store))
    if (path.endsWith('/stream')) return route.fulfill({contentType:'text/event-stream', body:'event: ping\ndata: {}\n\n'})
    if (path.endsWith('/events') || path.endsWith('/timeline')) return reply([])
    if (path.endsWith('/chat')) return reply([{seq:1,event_id:'fixture-message',recorded_at:'2026-09-19T00:00:00Z',from:'researcher',to:'builder',task_id:'t1',purpose:'handoff',text:'これはUIテスト用のメッセージです。資料の要点をまとめ、次の担当へ渡します。',artifact_refs:[],reply_to:null}])
    throw new Error(`Unexpected API request: ${method} ${path}`)
  })
}
async function noOverflow(page) {
  const sizes = await page.evaluate(() => ({ width:innerWidth, content:document.documentElement.scrollWidth }))
  assert.ok(sizes.content <= sizes.width + 1, `horizontal overflow ${JSON.stringify(sizes)}`)
}
try {
  for (const [width, lang] of [[1440,'ja'],[390,'ja'],[320,'ja'],[768,'en']]) {
    const context = await browser.newContext({ viewport:{width,height:1000}, locale:lang === 'ja' ? 'ja-JP':'en-US', reducedMotion:'reduce' })
    const store = fixture(); await setup(context, store)
    const page = await context.newPage(), errors=[]
    page.on('pageerror', e => errors.push(e.message))
    await page.goto(base+'/settings'); await page.locator('.custom-bot-add').waitFor()
    await noOverflow(page)
    await page.locator('.custom-bot-add').focus(); await page.keyboard.press('Enter')
    const form = page.locator('#custom-bot-form')
    await form.waitFor()
    assert.equal(await form.locator('details').getAttribute('open'), null)
    assert.equal(await form.locator('input:visible, textarea:visible').count(),3)
    const emojiInput = form.locator('.bot-emoji-input')
    await emojiInput.fill('not an emoji')
    // Fast input selection after opening must not lose focus to deferred autofocus.
    assert.equal(await emojiInput.inputValue(), 'not an emoji')
    assert.equal(await form.getByLabel(lang==='ja'?'名前':'Name',{exact:true}).inputValue(), '')
    assert.equal(await emojiInput.getAttribute('aria-invalid'), 'true')
    await emojiInput.fill('👩🏽‍💻')
    assert.equal(await emojiInput.getAttribute('aria-invalid'), 'false')
    const pick = form.getByRole('button', {name:lang==='ja'?'パンダ':'Panda',exact:true})
    await pick.focus(); await page.keyboard.press('Space')
    assert.equal(await pick.getAttribute('aria-pressed'), 'true')
    await form.getByLabel(lang==='ja'?'名前':'Name',{exact:true}).fill(lang==='ja'?'リサーチパンダ':'Research Panda')
    await form.getByLabel(lang==='ja'?'任せたいこと':'What should this bot do?',{exact:true}).fill('Read supplied sources. Summarize without making up facts.')
    assert.ok(await form.locator('.custom-bot-preview-face').evaluate(e=>parseFloat(getComputedStyle(e).fontSize)) >= 32)
    await noOverflow(page)
    await page.screenshot({path:`${shots}/creator-${width}-${lang}${isWebkit?'-webkit':''}.png`,fullPage:true})
    const submit = form.locator('button[type=submit]')
    if (width===1440) {
      store.failNext=true
      await submit.click(); await page.locator('.bot-form-error').waitFor()
      assert.equal(await form.getByLabel('名前',{exact:true}).inputValue(),'リサーチパンダ')
      assert.equal(store.creates,0)
    }
    const before=store.attempts
    // Exercise rapid repeated form submission in one frame; the ref must gate both.
    await form.evaluate(e=>{e.requestSubmit();e.requestSubmit()})
    assert.equal(await submit.isDisabled(),true)
    await page.locator('#custom-bot-created').waitFor()
    assert.equal(store.attempts,before+1);assert.equal(store.creates,1)
    assert.equal(await form.count(),0)
    await page.locator('#custom-bot-created button').click()
    const card=page.locator(`#agent-card-${store.lastCreated.id}`)
    assert.equal(await card.evaluate(e=>e===document.activeElement),true)
    const toggle=card.getByRole('switch')
    await toggle.focus();await page.keyboard.press('Space')
    await page.waitForFunction(()=>document.querySelector('.bot-settings-card:last-child [role=switch]')?.getAttribute('aria-checked')==='false')
    await toggle.focus();await page.keyboard.press('Enter')
    await page.waitForFunction(()=>document.querySelector('.bot-settings-card:last-child [role=switch]')?.getAttribute('aria-checked')==='true')
    await page.reload();await page.locator(`#agent-card-${store.lastCreated.id}`).waitFor()
    assert.equal(await page.locator(`#agent-card-${store.lastCreated.id} .bot-custom-emoji`).textContent(),'🐼')
    await page.locator('.custom-bot-add').click()
    assert.equal(await page.locator('#custom-bot-form').getByLabel(lang==='ja'?'名前':'Name',{exact:true}).inputValue(),'')
    await noOverflow(page)
    await page.goto(base+'/runs/ui-fixture');await page.locator('.simple-bot').first().waitFor()
    const states=await page.locator('.simple-bot [data-bot-state]').evaluateAll(xs=>xs.map(e=>e.getAttribute('data-bot-state')))
    assert.deepEqual(states,['idle','researching','waiting','waiting','idle'])
    assert.equal(await page.locator('.simple-message [data-bot-state]').getAttribute('data-bot-state'),'idle')
    const animations=await page.locator('[data-bot-state]').evaluateAll(xs=>xs.map(e=>getComputedStyle(e).animationName))
    assert.ok(animations.every(x=>x==='none'))
    await noOverflow(page)
    await page.screenshot({path:`${shots}/workroom-${width}-${lang}${isWebkit?'-webkit':''}.png`,fullPage:true})
    assert.deepEqual(errors,[])
    results.push({width,lang,engine:isWebkit?'webkit':'chromium',passed:true,checks:['three inputs','emoji selection','compound emoji','no overflow','double submit','save & reload','keyboard switches','accurate states','reduced motion']})
    await context.close()
  }
  console.log(JSON.stringify({ok:true,results},null,2))
  writeFileSync(`${shots}/results${isWebkit?'-webkit':''}.json`,JSON.stringify({ok:true,fixture:'in-memory API; not model or backend acceptance',results},null,2))
} catch (error) {
  for (const context of browser.contexts()) for(const page of context.pages()) await page.screenshot({path:`${shots}/failure${isWebkit?'-webkit':''}.png`,fullPage:true}).catch(()=>{})
  console.error(error);process.exitCode=1
} finally { await browser.close(); await new Promise(r=>server.close(r)) }

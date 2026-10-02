#!/usr/bin/env node
/** Real saved work / issued keys / HTTP 200 held by CDP. No replacement response bytes. */
import { chromium } from 'playwright-core'
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { join } from 'node:path'
import { createHash } from 'node:crypto'

const cfg = JSON.parse(readFileSync(process.env.WORKROOM_RECOVERY_CONFIG, 'utf8'))
const sha = bytes => createHash('sha256').update(bytes).digest('hex')
const specs = [
  { id: 'manual_pending', kind: 'manual', route: 'detail', rep: 3, role: 'operator', width: 390 },
  ...['detail', 'chat', 'events'].map(route => ({ id: `deadline_${route}`, kind: 'deadline', route, rep: 3, role: route === 'events' ? 'viewer' : 'operator', width: route === 'events' ? 768 : 390 })),
  { id: 'loaded_poll', kind: 'loaded', route: 'all', rep: 2, role: 'operator', width: 390 },
]
const checkIds = ['issued_login', 'actual_200_held', 'pending_or_deadline_boundary', 'native_reload', 'fresh_three_gets', 'original_artifact_bytes', 'old_requests_released', 'identity_and_state_preserved', 'error_and_write_boundary']
mkdirSync(cfg.output, { mode: 0o700 })
const report = { status: 'RUNNING', cases: specs.map(s => ({ ...s, status: 'UNVERIFIED', checks: checkIds.map(id => ({ id, status: 'UNVERIFIED' })), measurements: {} })), cleanup: [], http: [], errors: [], writes: [] }
const save = () => writeFileSync(join(cfg.output, 'report.json'), JSON.stringify(report, null, 2) + '\n', { mode: 0o600 })
const delay = ms => new Promise(resolve => setTimeout(resolve, ms))
async function deadline(label, fn, ms = 10000) {
  let timer
  try { return await Promise.race([Promise.resolve().then(fn), new Promise((_, reject) => { timer = setTimeout(() => reject(new Error(label)), ms) })]) }
  finally { clearTimeout(timer) }
}
async function until(label, predicate, ms = 10000) {
  await deadline(label, async () => { while (!await predicate()) await delay(25) }, ms)
}
function check(item, id, good) {
  Object.assign(item.checks.find(x => x.id === id), { status: good ? 'PASS' : 'FAIL' }); save()
  if (!good) throw new Error(id)
}
async function clean(id, fn) {
  try { await deadline(id, fn, 5000); report.cleanup.push({ id, status: 'PASS' }) }
  catch (error) { report.cleanup.push({ id, status: 'FAIL', error: String(error) }) }
  save()
}
async function tabTo(page, target) {
  for (let i = 0; i < 80; i++) {
    if (await target.evaluate(el => document.activeElement === el)) return
    await page.keyboard.press('Tab')
  }
  throw new Error('native_tab_target_not_reached')
}
async function artifactBytes(page, source, en) {
  const reader = page.getByRole('region', { name: (en ? 'Result: ' : '成果物：') + source.artifact_name, exact: true })
  let digest
  await until('original artifact bytes', async () => {
    const text = await reader.locator('pre').textContent()
    digest = sha(Buffer.from(text ?? '', 'utf8'))
    return digest === source.artifact_sha256
  })
  return digest
}
let browser, server, stopping = false
const contexts = new Set()
async function runCase(item) {
  const source = cfg.records.find(r => r.rep === item.rep), en = item.role === 'viewer'
  const base = `/api/runs/${source.run_id}`
  const routeOf = url => ({ [base]: 'detail', [base + '/chat']: 'chat', [base + '/events']: 'events' })[new URL(url).pathname]
  const context = await browser.newContext({ locale: en ? 'en-US' : 'ja-JP', viewport: { width: item.width, height: 900 }, reducedMotion: 'reduce' })
  contexts.add(context)
  const page = await context.newPage(); page.setDefaultTimeout(10000); page.setDefaultNavigationTimeout(15000)
  let cdp, mode = 'pass', phase = 'before_login', closing = false, navigating = false, pressAt = null
  const held = [], requests = [], responses = [], failures = [], protocolErrors = [], pending = new Set(), requestPhases = new WeakMap(), cancelled = new Set()
  const track = promise => { pending.add(promise); promise.catch(error => protocolErrors.push(String(error))).finally(() => pending.delete(promise)) }
  page.on('request', req => {
    requestPhases.set(req, phase)
    if (!['GET', 'HEAD', 'OPTIONS'].includes(req.method())) report.writes.push({ case: item.id, phase, method: req.method(), path: new URL(req.url()).pathname })
    const route = routeOf(req.url()); if (route) requests.push({ route, at: Date.now(), phase })
  })
  page.on('response', res => {
    const path = new URL(res.url()).pathname, route = routeOf(res.url())
    report.http.push({ case: item.id, phase: requestPhases.get(res.request()), path, status: res.status() })
    if (route) responses.push({ route, at: Date.now(), phase: requestPhases.get(res.request()), status: res.status() })
  })
  page.on('requestfailed', req => failures.push({ route: routeOf(req.url()), phase: requestPhases.get(req), error: req.failure()?.errorText, closing, navigation: navigating && req.isNavigationRequest() && req.resourceType() === 'document' }))
  page.on('pageerror', error => report.errors.push({ case: item.id, error: String(error) }))
  const expectedFailure = f => f.error === 'net::ERR_ABORTED' && (f.navigation || f.closing || (f.route && ['held_initial', 'held_poll'].includes(f.phase)))
  const boundariesGood = () => !report.http.some(h => h.case === item.id && h.status >= 400 && !(h.path === '/api/auth/me' && h.phase === 'before_login' && h.status === 401))
    && !report.writes.some(w => w.case === item.id && !(w.phase === 'login' && w.method === 'POST' && w.path === '/api/auth/login'))
    && !failures.some(f => !expectedFailure(f)) && !protocolErrors.length && !report.errors.some(e => e.case === item.id)
  async function navigate(url) { navigating = true; try { await page.goto(url) } finally { navigating = false } }
  item.status = 'RUNNING'; save()
  try {
    await navigate(cfg.origin + '/runs')
    await page.locator('#access-key').fill(readFileSync(cfg.credentials[item.role], 'utf8').trim())
    phase = 'login'
    const login = page.waitForResponse(r => new URL(r.url()).pathname === '/api/auth/login')
    await page.getByRole('button', { name: en ? 'Sign in' : 'ログイン', exact: true }).click()
    check(item, 'issued_login', (await login).status() === 200)
    await page.locator('.work-list').waitFor()
    const baselineResponse = await context.request.get(cfg.origin + base)
    if (baselineResponse.status() !== 200) throw new Error('actual_baseline_detail')
    const baseline = await baselineResponse.json()
    cdp = await context.newCDPSession(page)
    await cdp.send('Network.enable')
    cdp.on('Network.loadingFailed', e => { if (e.canceled && e.errorText === 'net::ERR_ABORTED') cancelled.add(e.requestId) })
    cdp.on('Fetch.requestPaused', e => {
      const route = routeOf(e.request.url)
      if (mode === 'hold' && route && (item.route === 'all' || route === item.route) && e.request.method === 'GET' && e.responseStatusCode === 200) {
        held.push({ id: e.requestId, networkId: e.networkId, route, at: Date.now(), status: e.responseStatusCode, phase }); save()
      } else track(deadline('continue actual response', () => cdp.send('Fetch.continueRequest', { requestId: e.requestId }), 3000))
    })
    await cdp.send('Fetch.enable', { patterns: [{ urlPattern: cfg.origin + base + '*', requestStage: 'Response' }] })
    phase = item.kind === 'loaded' ? 'loaded_initial' : 'held_initial'
    mode = item.kind === 'loaded' ? 'pass' : 'hold'
    await navigate(cfg.origin + `/runs/${source.run_id}?from=${source.status === 'completed' ? 'completed' : 'stopped'}`)
    let draft = null, statusText = null
    if (item.kind === 'loaded') {
      await artifactBytes(page, source, en)
      statusText = await page.locator('.work-status [role="status"] strong').textContent()
      await page.getByRole('button', { name: '会話', exact: true }).click()
      const section = page.locator('.conversation-direction')
      if (await section.count() && !await section.evaluate(el => el.open)) await section.locator(':scope > summary').click()
      if (typeof baseline.goal !== 'string' || !baseline.goal) throw new Error('original_goal_not_suitable_for_draft')
      // An unchanged prefix of the actual received request, never submitted.
      const original = Array.from(baseline.goal)
      draft = original.slice(0, 1024).join('')
      item.measurements.draft_source_goal_sha256 = sha(Buffer.from(baseline.goal, 'utf8'))
      item.measurements.draft_excerpt_sha256 = sha(Buffer.from(draft, 'utf8'))
      item.measurements.draft_source_codepoints = original.length
      item.measurements.draft_excerpt_codepoints = Array.from(draft).length
      await page.locator('#team-direction').fill(draft)
      await page.getByRole('button', { name: /^成果物\s/ }).click()
      mode = 'hold'; phase = 'held_poll'
    }
    await until('real 200 hold', () => held.length >= (item.route === 'all' ? 3 : 1))
    const firstHeldAt = held[0].at
    check(item, 'actual_200_held', held.every(h => h.status === 200) && (item.route !== 'all' || new Set(held.map(h => h.route)).size === 3))
    if (item.kind !== 'manual') {
      const error = item.kind === 'loaded'
        ? page.getByRole('alert').filter({ hasText: '最新の状態を取得できません。表示内容が古い可能性があります。' })
        : page.getByRole('heading', { name: en ? 'Could not open this work. Check your connection, then try again.' : 'この作業を読み込めませんでした。通信を確かめてから、もう一度お試しください。', exact: true })
      // The fixed product deadline is 15 s; an immediate failure must not pass.
      await delay(Math.max(0, 12000 - (Date.now() - firstHeldAt)))
      item.measurements.predeadline_observed_after_hold_ms = Date.now() - firstHeldAt
      let beforeDeadline = !await error.isVisible()
      if (item.kind === 'loaded') {
        beforeDeadline &&= await artifactBytes(page, source, en) === source.artifact_sha256
        await page.getByRole('button', { name: '会話', exact: true }).click()
        beforeDeadline &&= await page.locator('#team-direction').inputValue() === draft
        await page.getByRole('button', { name: /^成果物\s/ }).click()
      } else beforeDeadline &&= await page.locator('.simple-loading').isVisible()
      if (!beforeDeadline) check(item, 'pending_or_deadline_boundary', false)
      await error.waitFor({ timeout: Math.max(1, 22000 - (Date.now() - firstHeldAt)) })
      item.measurements.deadline_error_after_hold_ms = Date.now() - firstHeldAt
      check(item, 'pending_or_deadline_boundary', item.measurements.deadline_error_after_hold_ms <= 22000 && (item.kind === 'loaded' ? await page.locator('.simple-workroom').isVisible() : await page.locator('.simple-workroom').count() === 0))
      if (item.kind === 'loaded') {
        // Keep holding the next real poll. Manual reload must replace this unfinished batch.
        await until('next real held poll', () => ['detail', 'chat', 'events'].every(route => held.filter(h => h.route === route).length >= 2), 9000)
      }
    } else check(item, 'pending_or_deadline_boundary', await page.locator('.simple-loading').isVisible() && await page.locator('.simple-workroom').count() === 0)
    const target = item.kind === 'loaded' ? page.getByRole('alert').getByRole('button', { name: '再読み込み', exact: true }) : page.getByRole('button', { name: en ? 'Try again' : 'もう一度読み込む', exact: true })
    await deadline('natural tab to reload', () => tabTo(page, target), 10000)
    const beforePress = held.length
    mode = 'pass'; phase = 'explicit_reload'; pressAt = Date.now()
    await page.keyboard.press('Enter')
    item.measurements.enter_after_hold_ms = pressAt - firstHeldAt
    item.measurements.enter_after_initial_request_ms = pressAt - Math.min(...requests.filter(r => ['held_initial', 'loaded_initial'].includes(r.phase)).map(r => r.at))
    check(item, 'native_reload', beforePress > 0 && (item.kind !== 'manual' || item.measurements.enter_after_initial_request_ms < 2000))
    // Initial manual Enter precedes the first 5 s poll. The generous local/CI
    // 3 s response observation is an interaction check, not a performance SLA.
    await until('fresh three actual GETs', () => ['detail', 'chat', 'events'].every(route => requests.some(x => x.route === route && x.phase === 'explicit_reload' && x.at >= pressAt) && responses.some(x => x.route === route && x.phase === 'explicit_reload' && x.status === 200)), item.kind === 'manual' ? 3000 : 10000)
    check(item, 'fresh_three_gets', true)
    item.measurements.recovery_after_enter_ms = Date.now() - pressAt
    item.measurements.artifact_sha256 = await artifactBytes(page, source, en)
    check(item, 'original_artifact_bytes', item.measurements.artifact_sha256 === source.artifact_sha256)
    await until('held requests cancelled by application', () => held.every(h => h.networkId && cancelled.has(h.networkId)), 5000)
    item.measurements.old_cancelled_count = held.length
    for (const h of held) {
      try { await deadline('release old real response', () => cdp.send('Fetch.continueRequest', { requestId: h.id }), 3000); h.release = 'continued' }
      catch (error) {
        if (!cancelled.has(h.networkId) || !/Invalid (?:InterceptionId|interceptionId)|Invalid requestId|No resource with given identifier|Could not find request/.test(String(error))) throw error
        h.release = 'already_cancelled'
      }
    }
    await delay(300)
    check(item, 'old_requests_released', held.every(h => h.release))
    const finalResponse = await context.request.get(cfg.origin + base), final = await finalResponse.json()
    const identity = finalResponse.status() === 200 && final.run_id === baseline.run_id && final.status === baseline.status && final.last_seq === baseline.last_seq && new URL(page.url()).pathname === `/runs/${source.run_id}`
    let preservedDraft = true, preservedStatus = true
    if (item.kind === 'loaded') {
      preservedStatus = await page.locator('.work-status [role="status"] strong').textContent() === statusText
      await page.getByRole('button', { name: '会話', exact: true }).click()
      preservedDraft = await page.locator('#team-direction').inputValue() === draft
      await page.getByRole('button', { name: /^成果物\s/ }).click()
    }
    check(item, 'identity_and_state_preserved', identity && preservedDraft && preservedStatus && await artifactBytes(page, source, en) === source.artifact_sha256)
    item.measurements.held_200_by_route = Object.fromEntries(['detail', 'chat', 'events'].map(route => [route, held.filter(h => h.route === route).length]))
    item.measurements.draft_preserved = item.kind === 'loaded' ? preservedDraft : null
    item.measurements.identity_status_last_seq_preserved = identity
    item.measurements.expected_abort_count = failures.filter(f => f.route && f.error === 'net::ERR_ABORTED' && ['held_initial', 'held_poll'].includes(f.phase)).length
    check(item, 'error_and_write_boundary', boundariesGood())
    item.status = 'PASS'
  } catch (error) {
    item.status = 'FAIL'; item.error_type = error.name; item.error = String(error); save()
  } finally {
    item.held = held; item.requests = requests; item.responses = responses; item.failures = failures; item.protocol_errors = protocolErrors
    closing = true
    if (cdp) await clean(item.id + '-fetch-disable', () => cdp.send('Fetch.disable'))
    await clean(item.id + '-pending-cdp', () => Promise.allSettled([...pending]))
    await clean(item.id + '-context', () => context.close()); contexts.delete(context)
    // Late CDP rejection / page error must invalidate a previously passing case.
    if (!boundariesGood()) {
      item.status = 'FAIL'
      Object.assign(item.checks.find(x => x.id === 'error_and_write_boundary'), { status: 'FAIL' })
    }
    if (report.cleanup.some(c => c.id.startsWith(item.id + '-') && c.status === 'FAIL')) item.status = 'FAIL'
    save()
  }
}
try {
  const url = new URL(cfg.origin)
  if (url.protocol !== 'http:' || url.hostname !== '127.0.0.1') throw new Error('loopback_only')
  await deadline('whole browser recovery suite', async () => {
    server = await chromium.launchServer({ ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : { channel: 'chrome' }), headless: true, timeout: 20000 })
    browser = await chromium.connect(server.wsEndpoint(), { timeout: 15000 }); report.chrome_version = browser.version()
    for (const item of report.cases) { if (stopping) break; await runCase(item) }
  }, 160000)
  report.status = report.cases.every(c => c.status === 'PASS') ? 'PASS' : 'FAIL'
} catch (error) { stopping = true; report.status = 'FAIL'; report.error_type = error.name; report.error = String(error) }
finally {
  stopping = true
  for (const context of contexts) await clean('remaining-context', () => context.close())
  if (browser) await clean('browser-close', () => browser.close())
  if (server) await clean('owned-chrome-close', () => server.close())
  if (report.cleanup.some(c => c.status !== 'PASS')) report.status = 'FAIL'
  save()
}
console.log(JSON.stringify({ status: report.status, passed_cases: report.cases.filter(c => c.status === 'PASS').length }))
if (report.status !== 'PASS') process.exitCode = 1

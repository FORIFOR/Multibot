#!/usr/bin/env node
/** Actual Chrome / real AppService read-only regression. No route/response mocks.
 * Invoked by check_result_reading.py with private file references in RESULT_READING_CONFIG.
 * Only login POSTs are performed. All screenshots, response metadata and raw errors are private.
 */
import { chromium } from 'playwright-core'
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createHash } from 'node:crypto'

const cfg = JSON.parse(readFileSync(process.env.RESULT_READING_CONFIG, 'utf8'))
const out = cfg.output
mkdirSync(out, { recursive: false, mode: 0o700 })
const sha = bytes => createHash('sha256').update(bytes).digest('hex')
const ids = ['default_results', 'artifact_bytes', 'filename_h2', 'team_closed', 'keyboard_open', 'poll_preserves_open',
  'keyboard_close', 'conversation_roundtrip', 'incomplete_warning', 'from_filter', 'overflow', 'permission_controls']
const report = { status: 'RUNNING', started_at: new Date().toISOString(), script_sha256: sha(readFileSync(fileURLToPath(import.meta.url))),
  cases: [], http: [], failed_requests: [], console_errors: [], page_errors: [], writes: [], cleanup: [], screenshots: [],
  limits: ['Real desktop Chrome at narrow viewports; not a physical phone or a screen reader test.',
    'Operator uses Japanese and viewer uses English; not all role/language combinations.',
    'Source AI findings are preserved, not accepted as correct. No adoption, export, resume, instruction, or model execution.'] }
for (const role of ['operator', 'viewer']) for (const width of [390, 320]) for (const source of cfg.records)
  report.cases.push({ id: `${role}-${width}-rep${source.rep}`, role, width, rep: source.rep, recorded_status: source.status,
    status: 'UNVERIFIED', checks: ids.map(id => ({ id, status: 'UNVERIFIED' })) })
let browser, server, stopping = false
const contexts = new Set()
const save = () => writeFileSync(join(out, 'report.json'), JSON.stringify(report, null, 2) + '\n', { mode: 0o600 })
writeFileSync(join(out, 'runner-source.mjs'), readFileSync(fileURLToPath(import.meta.url)), { mode: 0o600 })
const deadline = async (label, fn, ms = 10000) => {
  let timer
  try { return await Promise.race([Promise.resolve().then(fn), new Promise((_, reject) => { timer = setTimeout(() => reject(new Error(`${label} timed out`)), ms) })]) }
  finally { clearTimeout(timer) }
}
const cleanup = async (id, fn) => {
  try { await deadline(id, fn); report.cleanup.push({ id, status: 'PASS' }) }
  catch (error) { report.cleanup.push({ id, status: 'FAIL', error_type: error.name, error: String(error) }) }
}
function check(item, id, good, measurement) {
  const record = item.checks.find(x => x.id === id)
  Object.assign(record, { status: good ? 'PASS' : 'FAIL', ...(measurement ? { measurement } : {}) })
  save()
  if (!good) throw new Error(`Check failed: ${item.id}/${id}`)
}
async function tabTo(page, target) {
  for (let i = 0; i < 45; i++) {
    if (await target.evaluate(el => document.activeElement === el)) return i
    await page.keyboard.press('Tab')
  }
  throw new Error('Native Tab traversal did not reach the team summary')
}
async function shot(page, name) {
  await deadline('screenshot', () => page.screenshot({ path: join(out, name), fullPage: false }))
  report.screenshots.push(name)
}
async function artifactBytes(reader, expected) {
  const until = Date.now() + 10000
  const samples = []
  while (Date.now() < until) {
    const text = await reader.locator('pre').textContent()
    const bytes = Buffer.from(text ?? '', 'utf8')
    const digest = sha(bytes)
    if (samples.at(-1)?.sha256 !== digest) samples.push({ sha256: digest, utf8_bytes: bytes.length })
    if (digest === expected) return { sha256: digest, samples }
    await new Promise(resolve => setTimeout(resolve, 100))
  }
  const error = new Error('Rendered artifact did not match preserved UTF-8 bytes within 10 seconds')
  error.hash_samples = samples
  throw error
}
function monitor(page, label, state) {
  const requests = new WeakMap()
  page.on('pageerror', e => report.page_errors.push({ scope: label, error: String(e) }))
  page.on('console', m => {
    if (m.type() !== 'error') return
    let path = ''
    try { path = new URL(m.location().url).pathname } catch {}
    report.console_errors.push({ scope: label, text: m.text(), expected_prelogin_auth:
      state.phase === 'before_login' && path === '/api/auth/me' && /\b401\b/.test(m.text()) })
  })
  page.on('request', request => {
    requests.set(request, { phase: state.phase, epoch: state.epoch })
    if (!['GET', 'HEAD', 'OPTIONS'].includes(request.method())) report.writes.push({ method: request.method(), path: new URL(request.url()).pathname })
  })
  page.on('response', response => {
    const url = new URL(response.url())
    report.http.push({ scope: label, path: url.pathname, status: response.status(), time: Date.now(),
      expected_prelogin_auth: url.pathname === '/api/auth/me' && response.status() === 401 &&
        requests.get(response.request())?.phase === 'before_login' })
  })
  page.on('requestfailed', request => report.failed_requests.push({ scope: label, path: new URL(request.url()).pathname,
    error: request.failure()?.errorText, resource_type: request.resourceType(), abort_reason:
      state.closing ? 'owned_context_close' : requests.get(request)?.epoch < state.epoch ? 'replaced_document' : null }))
}
async function runCases() {
  const origin = new URL(cfg.origin)
  if (origin.hostname !== '127.0.0.1' || origin.protocol !== 'http:') throw new Error('Only real loopback AppService is allowed')
  server = await deadline('chrome launch', () => chromium.launchServer({
    ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : { channel: 'chrome' }),
    headless: true, timeout: 20000,
  }), 25000)
  report.owned_chrome_pid = server.process().pid
  browser = await deadline('chrome connect', () => chromium.connect(server.wsEndpoint(), { timeout: 15000 }), 20000)
  report.chrome_version = browser.version()
  for (const role of ['operator', 'viewer']) for (const width of [390, 320]) {
    if (stopping) return
    const en = role === 'viewer'
    const context = await deadline('context creation', () => browser.newContext({ locale: en ? 'en-US' : 'ja-JP', viewport: { width, height: 900 }, reducedMotion: 'reduce' }))
    contexts.add(context)
    const page = await deadline('page creation', () => context.newPage())
    page.setDefaultTimeout(10000); page.setDefaultNavigationTimeout(15000)
    const state = { phase: 'before_login', epoch: 0, closing: false }
    monitor(page, `${role}-${width}`, state)
    const navigate = async url => { state.epoch += 1; await page.goto(url) }
    try {
      await navigate(cfg.origin + '/runs')
      await page.locator('#access-key').fill(readFileSync(cfg.credentials[role], 'utf8').trim())
      state.phase = 'logging_in'
      const login = page.waitForResponse(response => new URL(response.url()).pathname === '/api/auth/login', { timeout: 10000 })
      await page.getByRole('button', { name: en ? 'Sign in' : 'ログイン', exact: true }).click()
      if ((await login).status() !== 200) throw new Error('Real issued-key login failed')
      state.phase = 'authenticated'
      await page.locator('.work-list').waitFor()
      for (const source of cfg.records) {
        if (stopping) return
        const item = report.cases.find(x => x.role === role && x.width === width && x.rep === source.rep)
        item.status = 'RUNNING'; item.started_at = new Date().toISOString(); save()
        try {
          const filter = source.status === 'completed' ? 'completed' : 'stopped'
          await navigate(cfg.origin + '/runs?filter=' + filter)
          const link = page.locator(`.work-item[href^="/runs/${source.run_id}?"]`)
          await link.waitFor()
          const href = await link.getAttribute('href')
          await link.click()
          const room = page.locator('.simple-workroom')
          const reader = page.getByRole('region', { name: (en ? 'Result: ' : '成果物：') + source.artifact_name, exact: true })
          await reader.waitFor(); await reader.locator('pre').waitFor()
          check(item, 'default_results', await room.getAttribute('data-studio-panel') === 'results' && await reader.isVisible())
          const initialBytes = await deadline('actual artifact byte match', () => artifactBytes(reader, source.artifact_sha256), 15000)
          check(item, 'artifact_bytes', initialBytes.sha256 === source.artifact_sha256, initialBytes)
          check(item, 'filename_h2', await page.locator('.result-file-identity').getByRole('heading', { level: 2, name: source.artifact_name, exact: true }).count() === 1)
          const team = page.locator('.team-disclosure')
          const summary = team.locator(':scope > summary')
          check(item, 'team_closed', !(await team.evaluate(el => el.open)) && await summary.isVisible())
          await page.evaluate(() => scrollTo(0, 0))
          await shot(page, item.id + '-top.png')
          const tabs = await deadline('native tab traversal', () => tabTo(page, summary), 15000)
          await page.keyboard.press('Enter')
          await page.waitForFunction(() => document.querySelector('.team-disclosure')?.open === true)
          check(item, 'keyboard_open', await summary.evaluate(el => document.activeElement === el), { tab_presses: tabs, key: 'Enter' })
          const path = '/api/runs/' + source.run_id
          const beforePoll = report.http.filter(x => x.path === path && x.status === 200).length
          const poll = page.waitForResponse(response => new URL(response.url()).pathname === path && response.status() === 200, { timeout: 12000 })
          await Promise.all([poll, deadline('six second real poll interval', () => new Promise(resolve => setTimeout(resolve, 6000)), 8000)])
          const observedPolls = report.http.filter(x => x.path === path && x.status === 200).length - beforePoll
          const polledBytes = await deadline('polled artifact byte match', () => artifactBytes(reader, source.artifact_sha256), 15000)
          check(item, 'poll_preserves_open', observedPolls >= 1 && await team.evaluate(el => el.open) &&
            await summary.evaluate(el => document.activeElement === el), { observed_detail_responses: observedPolls, minimum_wait_ms: 6000,
              artifact_sha256: polledBytes.sha256, samples: polledBytes.samples })
          await page.keyboard.press('Space')
          await page.waitForFunction(() => document.querySelector('.team-disclosure')?.open === false)
          check(item, 'keyboard_close', !(await team.evaluate(el => el.open)), { key: 'Space' })
          await page.getByRole('button', { name: en ? 'Conversation' : '会話', exact: true }).click()
          await page.waitForFunction(() => document.querySelector('.simple-workroom')?.dataset.studioPanel === 'team')
          await page.getByRole('button', { name: en ? /^Results\s/ : /^成果物\s/ }).click()
          await reader.waitFor()
          check(item, 'conversation_roundtrip', await room.getAttribute('data-studio-panel') === 'results' && !(await team.evaluate(el => el.open)))
          const warning = page.getByText(en ? 'The request is not complete. These are the available partial results.' : '依頼全体は完了していません。使える途中成果を確認できます。', { exact: true })
          check(item, 'incomplete_warning', source.status === 'completed' ? await warning.count() === 0 : await warning.isVisible())
          const adoptCount = await page.locator('[data-adopt]').count()
          check(item, 'permission_controls', role === 'viewer' ? adoptCount === 0 && await page.locator('.desk-resume').count() === 0 : adoptCount === 1)
          const dimensions = await page.evaluate(() => ({ viewport: innerWidth, document: document.documentElement.scrollWidth, body: document.body.scrollWidth }))
          check(item, 'overflow', dimensions.document <= width && dimensions.body <= width, dimensions)
          await reader.scrollIntoViewIfNeeded(); await shot(page, item.id + '-reader.png')
          await page.getByRole('link', { name: en ? '← Back to work' : '← 作業一覧に戻る', exact: true }).click()
          await page.locator('.work-list').waitFor()
          check(item, 'from_filter', href === `/runs/${source.run_id}?from=${filter}` && new URL(page.url()).searchParams.get('filter') === filter)
          item.status = 'PASS'
        } catch (error) {
          item.status = 'FAIL'; item.error_type = error.name; item.error = String(error)
          if (error.hash_samples) item.hash_samples = error.hash_samples
          try { await shot(page, item.id + '-failure.png') } catch (captureError) { item.capture_error_type = captureError.name }
        } finally { item.finished_at = new Date().toISOString(); save() }
      }
    } finally { state.closing = true; await cleanup(`${role}-${width}-context`, () => context.close()); contexts.delete(context) }
  }
}
try {
  await deadline('whole browser suite', runCases, 210000)
  const unexpectedHttp = report.http.filter(x => x.status >= 400 && !x.expected_prelogin_auth)
  const expectedAbort = x => x.error === 'net::ERR_ABORTED' && x.resource_type === 'document' && x.abort_reason
  const aborted = report.failed_requests.filter(expectedAbort)
  const unexpectedNetwork = report.failed_requests.filter(x => !expectedAbort(x))
  const unexpectedConsole = report.console_errors.filter(x => !x.expected_prelogin_auth)
  report.network_summary = { http_errors: unexpectedHttp.length, expected_auth_401: report.http.filter(x => x.expected_prelogin_auth).length,
    failed_requests: unexpectedNetwork.length, navigation_aborts: aborted.length,
    unexpected_console_errors: unexpectedConsole.length,
    unauthorized_write_requests: report.writes.filter(x => x.method !== 'POST' || x.path !== '/api/auth/login').length }
  report.status = report.cases.every(x => x.status === 'PASS') && !unexpectedHttp.length && !unexpectedNetwork.length &&
    !report.page_errors.length && !unexpectedConsole.length && !report.network_summary.unauthorized_write_requests ? 'PASS' : 'FAIL'
} catch (error) { stopping = true; report.status = 'FAIL'; report.error_type = error.name; report.error = String(error) }
finally {
  stopping = true
  for (const context of contexts) await cleanup('remaining-context', () => context.close())
  if (browser) await cleanup('browser-close', () => browser.close())
  if (server) await cleanup('owned-chrome-close', () => server.close())
  if (report.cleanup.some(x => x.status !== 'PASS')) report.status = 'FAIL'
  report.finished_at = new Date().toISOString(); save()
}
console.log(JSON.stringify({ status: report.status, cases: report.cases.length, passed: report.cases.filter(x => x.status === 'PASS').length }))
if (report.status !== 'PASS') process.exitCode = 1

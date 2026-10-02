/** Actual Chrome transport failure and explicit reload against the issued-key API.
 * CDP blocks requests, never fabricates responses. No work or model is started.
 * Only initial-recovery.json is public; errors remain in a private log.
 */
import { chromium } from 'playwright-core'
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'

const origin = process.env.AUTH_TEST_URL
const keyFile = process.env.AUTH_TEST_OPERATOR_KEY_FILE
const subject = process.env.AUTH_TEST_OPERATOR_SUBJECT
const data = process.env.AUTH_TEST_DATA_DIR
const out = process.env.AUTH_TEST_EVIDENCE_DIR
const repo = fileURLToPath(new URL('../../', import.meta.url))
const report = { status: 'RUNNING', method: 'Actual CDP Network.setBlockedURLs, real API, issued key and SQLite',
  planned_cases: 2, cases: [], writes: [], cleanup: [], source_sha256: null,
  source_unchanged: null, business_before: null, business_after: null,
  model_execution_requested: false, human_acceptance: 'not_performed',
  limits: ['Initial unauthenticated JA390 status / EN768 me failures only; no SSO or existing-session acceptance.',
    'Five seconds without automatic recovery is an observation window, not an indefinite guarantee.',
    'No screenshots, raw API bodies, credentials, database, or exception messages are public.',
    'Browser process drainage is measured by the parent check_public_service runner.'] }
let browser, key, failureCheck = 'validate_configuration', initialized = false
const sources = ['frontend/scripts/auth-initial-recovery.mjs', 'frontend/src/components/AuthGate.tsx',
  'frontend/src/lib/browser-session.ts', 'backend/scripts/check_public_service.py',
  'docs/evidence/real-readiness-v61-qwen35-fixed-20260925/01-run_1a0d74b88812173eb2c-run.json']
const sha = bytes => createHash('sha256').update(bytes).digest('hex')
const hashes = () => Object.fromEntries(sources.map(name => [name, sha(readFileSync(resolve(repo, name)))]))
const ensure = (value, id) => { failureCheck = id; if (!value) throw new Error(id) }
const save = () => {
  const text = JSON.stringify(report, null, 2) + '\n'
  if (key && text.includes(key)) throw new Error('safe_report_excludes_issued_key')
  writeFileSync(resolve(out, 'initial-recovery.json'), text, { mode: 0o600 })
}
const privateFailure = error => {
  try { writeFileSync(resolve(out, 'initial-recovery.private.log'), String(error?.stack || error) + '\n', { mode: 0o600, flag: 'a' }) }
  catch { report.private_log_write_failed = true }
}
const counts = () => {
  const value = JSON.parse(execFileSync('sqlite3', ['-readonly', '-json', resolve(data, 'agentteam.sqlite'),
    "SELECT (SELECT count(*) FROM runs) AS runs,(SELECT count(*) FROM execution_jobs) AS jobs,(SELECT count(*) FROM events WHERE type LIKE 'model.%') AS model_events,(SELECT count(*) FROM artifacts) AS artifacts;"],
    { encoding: 'utf8', timeout: 5000 }))[0]
  ensure(Object.values(value).every(n => Number.isSafeInteger(n) && n >= 0), 'sqlite_counts_valid')
  return value
}
const end = Date.now() + 90000
async function bounded(promise, id, maximum = 15000, cleanup = false) {
  failureCheck = id
  let timer
  const remaining = cleanup ? maximum : Math.min(maximum, Math.max(1, end - Date.now()))
  try { return await Promise.race([promise, new Promise((_, reject) => { timer = setTimeout(() => reject(new Error(id)), remaining) })]) }
  finally { clearTimeout(timer) }
}
async function close(name, action) {
  try { await bounded(action(), 'owned_cleanup', 10000, true); report.cleanup.push({ name, status: 'PASS' }) }
  catch (error) { report.status = 'FAIL'; report.cleanup.push({ name, status: 'FAIL' }); privateFailure(error) }
}

try {
  ensure(origin && keyFile && subject && data && out, 'explicit_private_configuration')
  ensure(['localhost', '127.0.0.1'].includes(new URL(origin).hostname), 'loopback_only')
  mkdirSync(out, { recursive: true, mode: 0o700 })
  writeFileSync(resolve(out, 'initial-recovery.json'), '{}\n', { mode: 0o600, flag: 'wx' })
  initialized = true
  key = readFileSync(keyFile, 'utf8').trim()
  ensure(key.length >= 32, 'issued_key_file')
  report.source_sha256 = hashes()
  report.business_before = counts()
  save()
  browser = await bounded(chromium.launch({ channel: 'chrome', timeout: 15000 }), 'chrome_launch')
  report.browser = browser.version()
  for (const test of [{ id: 'ja390-status', lang: 'ja', width: 390, path: '/api/auth/status' },
    { id: 'en768-me', lang: 'en', width: 768, path: '/api/auth/me' }]) {
    const item = { id: test.id, status: 'RUNNING', checks: [], http: [], failed_requests: [], page_error_count: 0 }
    report.cases.push(item)
    let context, phase = 'initial_failure'
    const requestPhases = new WeakMap()
    const knownRoutes = ['/api/auth/status', '/api/auth/me', '/api/auth/login', '/api/config', '/api/runs', '/api/health', '/api/approvals', '/api/usage']
    const route = request => { const path = new URL(request.url()).pathname; return knownRoutes.includes(path) ? path : 'other' }
    const pass = id => { item.checks.push(id); save() }
    try {
      context = await bounded(browser.newContext({ locale: test.lang === 'ja' ? 'ja-JP' : 'en-US', viewport: { width: test.width, height: 844 } }), 'context_create')
      const page = await bounded(context.newPage(), 'page_create')
      page.setDefaultTimeout(10000); page.setDefaultNavigationTimeout(10000)
      page.on('pageerror', () => { item.page_error_count++ })
      page.on('request', request => {
        requestPhases.set(request, phase)
        if (!['GET', 'HEAD', 'OPTIONS'].includes(request.method())) report.writes.push({ case: test.id, phase, method: request.method(), route: route(request) })
      })
      page.on('response', response => {
        if (new URL(response.url()).pathname.startsWith('/api/')) item.http.push({ phase: requestPhases.get(response.request()), route: route(response.request()), status: response.status() })
      })
      page.on('requestfailed', request => {
        const at = requestPhases.get(request)
        const expected = route(request) === test.path && ['initial_failure', 'blocked_reload'].includes(at)
        const aborted = request.failure()?.errorText === 'net::ERR_ABORTED'
        const navigationAbort = request.resourceType() === 'document' && aborted && ['blocked_reload', 'restored_reload'].includes(at)
        item.failed_requests.push({ phase: at, route: route(request), expected_block: expected, expected_navigation_abort: navigationAbort, context_close_abort: phase === 'closing' && aborted })
      })
      const cdp = await bounded(context.newCDPSession(page), 'cdp_connect')
      await bounded(cdp.send('Network.enable'), 'cdp_enable')
      await bounded(cdp.send('Network.setBlockedURLs', { urls: [origin + test.path] }), 'block_actual_transport')
      await page.goto(origin, { waitUntil: 'domcontentloaded' })
      const reload = page.getByRole('button', { name: test.lang === 'ja' ? '再読込して接続を確認' : 'Reload and check connection', exact: true })
      const failureBoundary = async () => {
        await page.getByRole('alert').waitFor()
        await reload.waitFor()
        ensure(await reload.isEnabled(), 'explicit_reload_enabled')
        ensure(await page.locator('#access-key, .shell-side, a[href^="/oauth2/"]').count() === 0, 'failure_hides_auth_and_workspace')
      }
      const keyboardReload = async () => {
        let focused = false
        for (let i = 0; i < 8 && !focused; i++) {
          await page.keyboard.press('Tab')
          focused = await reload.evaluate(element => element === document.activeElement)
        }
        ensure(focused, 'reload_reachable_by_native_tab')
        await Promise.all([page.waitForEvent('domcontentloaded', { timeout: 10000 }), page.keyboard.press('Enter')])
      }
      await failureBoundary()
      ensure(item.failed_requests.some(r => r.phase === 'initial_failure' && r.expected_block), 'actual_initial_request_blocked')
      pass('initial_failure_explicit_reload_and_no_auth_controls')
      phase = 'blocked_reload'
      await keyboardReload()
      await failureBoundary()
      ensure(item.failed_requests.some(r => r.phase === 'blocked_reload' && r.expected_block), 'blocked_reload_repeats_actual_failure')
      pass('keyboard_reload_while_blocked_preserves_failure_boundary')
      phase = 'restored_without_reload'
      await bounded(cdp.send('Network.setBlockedURLs', { urls: [] }), 'restore_actual_transport')
      const before = item.http.length
      await bounded(page.waitForTimeout(5000), 'five_second_observation', 6000)
      await failureBoundary()
      ensure(item.http.length === before, 'no_automatic_auth_requests_in_observation_window')
      pass('restored_transport_waits_for_explicit_reload_for_five_seconds')
      phase = 'restored_reload'
      await keyboardReload()
      const login = page.getByRole('button', { name: test.lang === 'ja' ? 'ログイン' : 'Sign in', exact: true })
      await login.waitFor()
      await page.waitForFunction(() => document.querySelector('form button')?.disabled === false)
      ensure(await page.getByRole('alert').count() === 0 && await reload.count() === 0, 'connection_error_cleared')
      ensure(await page.locator('#access-key').inputValue() === '', 'reload_does_not_prefill_secret')
      ensure(item.http.some(r => r.phase === phase && r.route === '/api/auth/status' && r.status === 200) && item.http.some(r => r.phase === phase && r.route === '/api/auth/me' && r.status === 401), 'actual_unauthenticated_recovery_responses')
      pass('keyboard_reload_restores_empty_enabled_login')
      phase = 'issued_key_login'
      await page.locator('#access-key').fill(key)
      await login.click()
      await page.locator('.shell-side').waitFor()
      const me = await context.request.get(origin + '/api/auth/me', { timeout: 10000 })
      const principal = await bounded(me.json(), 'read_authenticated_identity')
      ensure(me.status() === 200 && principal.subject === subject && principal.role === 'operator', 'actual_issued_operator_identity')
      ensure(item.http.some(r => r.phase === phase && r.route === '/api/auth/login' && r.status === 200), 'actual_login_http_200')
      pass('actual_issued_operator_login_and_identity')
      ensure(item.page_error_count === 0 && item.failed_requests.every(r => r.expected_block || r.expected_navigation_abort), 'no_unexpected_browser_failures')
      ensure(item.http.every(r => r.status < 400 || (r.route === '/api/auth/me' && r.status === 401 && r.phase === 'restored_reload')), 'http_failures_limited_to_expected_unauthenticated_response')
      pass('http_and_browser_error_boundaries')
      item.status = 'PASS'
    } catch (error) { item.status = 'FAIL'; throw error }
    finally { phase = 'closing'; if (context) await close(test.id + '-context', () => context.close()); save() }
  }
  ensure(report.writes.length === 2 && report.writes.every(r => r.route === '/api/auth/login' && r.method === 'POST' && r.phase === 'issued_key_login'), 'only_two_explicit_logins_write')
  ensure(report.cases.every(c => c.page_error_count === 0 && c.failed_requests.every(r => r.expected_block || r.expected_navigation_abort || r.context_close_abort)), 'late_browser_errors_checked_after_context_close')
  ensure(report.cases.every(c => c.http.every(r => r.status < 400 || (r.route === '/api/auth/me' && r.status === 401 && r.phase === 'restored_reload'))), 'late_http_errors_checked_after_context_close')
  if (report.status !== 'FAIL') report.status = 'PASS'
} catch (error) {
  report.status = 'FAIL'; report.failure_check = failureCheck
  report.error_type = ['Error', 'TimeoutError', 'TypeError'].includes(error?.name) ? error.name : 'OtherError'
  if (initialized) privateFailure(error)
} finally {
  if (browser) await close('browser', () => browser.close())
  if (initialized) {
    try {
      report.business_after = counts()
      report.source_unchanged = report.source_sha256 ? JSON.stringify(hashes()) === JSON.stringify(report.source_sha256) : null
      if (JSON.stringify(report.business_after) !== JSON.stringify(report.business_before) || !report.source_unchanged) report.status = 'FAIL'
    } catch (error) { report.status = 'FAIL'; privateFailure(error) }
    try { save() } catch (error) { report.status = 'FAIL'; privateFailure(error) }
  }
}
console.log(JSON.stringify({ status: report.status, completed_cases: report.cases.filter(c => c.status === 'PASS').length }))
if (report.status !== 'PASS') process.exitCode = 1

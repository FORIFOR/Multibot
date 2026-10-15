/** Actual Chrome + HTTP/SQLite: a sign-in tab leaves while its real HTTP 200 is held.
 * CDP changes response timing only; credentials are issued by the actual application.
 * No work is submitted and no model is called. Baseline mode preserves the known failure.
 */
import { chromium } from 'playwright-core'
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'
import assert from 'node:assert/strict'

const origin = process.env.AUTH_TEST_URL
const admin = process.env.AUTH_TEST_ADMIN_KEY_FILE
const operator = process.env.AUTH_TEST_OPERATOR_KEY_FILE
const data = process.env.AUTH_TEST_DATA_DIR
const out = process.env.AUTH_TEST_EVIDENCE_DIR
const baseline = process.env.AUTH_PEER_EXPECT === 'stuck'
assert.ok(origin && admin && operator && data && out)
assert.ok(['localhost', '127.0.0.1'].includes(new URL(origin).hostname))
const repo = fileURLToPath(new URL('../../', import.meta.url))
const sourcePath = resolve(repo, 'docs/PRODUCTION_PLAN.md')
const source = readFileSync(sourcePath, 'utf8')
const goal = source.split('\n').find(line => line.startsWith('Goal:'))
assert.ok(goal)
const counts = () => JSON.parse(execFileSync('sqlite3', ['-json', resolve(data, 'agentteam.sqlite'), "SELECT (SELECT count(*) FROM runs) AS runs, (SELECT count(*) FROM execution_jobs) AS jobs, (SELECT count(*) FROM events WHERE type='model.called') AS model_calls;"], { encoding: 'utf8' }))[0]
const initial = counts()
const key = path => readFileSync(path, 'utf8').trim()
const pause = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds))
const clean = async page => page.evaluate(() => {
  const draft = JSON.parse(sessionStorage.getItem('agentteam.requestDraft') || 'null')
  return (!draft || (!draft.goal && !draft.text && !draft.files.length)) &&
    !sessionStorage.getItem('agentteam.tabOwner') &&
    !sessionStorage.getItem('agentteam.pendingCommands') &&
    !sessionStorage.getItem('agentteam.draftGoal') &&
    !Object.keys(localStorage).some(name => name.startsWith('artifact-draft:'))
})
mkdirSync(out, { recursive: true })
let browser, current, cleanupError
const report = {
  started_at: new Date().toISOString(), status: 'RUNNING', mode: baseline ? 'original-code-reproduction' : 'fixed-code-verification',
  source: 'docs/PRODUCTION_PLAN.md', source_sha256: createHash('sha256').update(source).digest('hex'),
  checks: [], model_execution: false, human_acceptance: false,
  limitations: ['Local actual technical accounts; no external IdP/TLS acceptance', 'CDP holds actual HTTP 200 responses; it supplies no response bytes', 'For abrupt close, CDP stops sender JavaScript after HTTP 200 is held so no completion callback can run during tab departure', 'A suspended browser cannot render until it resumes; the lease is checked when its JavaScript runs'],
}
const save = () => writeFileSync(resolve(out, 'peer-tab-close.json'), JSON.stringify(report, null, 2) + '\n')
try {
  browser = await chromium.launch({ channel: 'chrome' })
  report.browser = browser.version()
  for (const departure of ['close', 'reload']) {
    const context = await browser.newContext({ locale: 'ja-JP', viewport: { width: 1280, height: 900 } })
    try {
      const observer = await context.newPage(), sender = await context.newPage()
      current = observer
      for (const page of [observer, sender]) { page.setDefaultTimeout(10000); await page.goto(origin); await page.locator('#access-key').waitFor() }
      await observer.locator('#access-key').fill(key(admin))
      await observer.getByRole('button', { name: 'ログイン', exact: true }).click()
      await observer.locator('#request-goal').waitFor()
      await observer.locator('#request-goal').fill(goal)
      await observer.locator('#run-attachments').setInputFiles(sourcePath)
      await observer.waitForFunction(() => JSON.parse(sessionStorage.getItem('agentteam.requestDraft') || 'null')?.files?.length === 1)
      await sender.locator('#access-key').waitFor()
      await sender.locator('#access-key').fill(key(operator))
      await observer.evaluate(() => {
        window.__peerNotifications = []
        const observe = message => window.__peerNotifications.push({ pending: message.pending === true })
        const channel = new BroadcastChannel('agentteam.sessionChange')
        channel.onmessage = event => observe(event.data)
        window.addEventListener('storage', event => { if (event.key === 'agentteam.sessionChange') observe(JSON.parse(event.newValue || '{}')) })
      })
      const client = await context.newCDPSession(sender)
      let held
      client.on('Fetch.requestPaused', event => { held = event })
      await client.send('Fetch.enable', { patterns: [{ urlPattern: '*/api/auth/login', requestStage: 'Response' }] })
      const observerStarted = await observer.evaluate(() => performance.now())
      const started = performance.now()
      await sender.getByRole('button', { name: 'ログイン', exact: true }).click()
      const responseDeadline = performance.now() + 5000
      while (!held && performance.now() < responseDeadline) await pause(20)
      assert.equal(held?.responseStatusCode, 200, 'The actual key must be accepted before its response is held.')
      await observer.getByRole('status').waitFor()
      assert.equal(await observer.locator('#request-goal').count(), 0)
      assert.ok(await clean(observer), 'The old draft and attachment must already be cleared before departure.')
      if (departure === 'close') {
        await client.send('Emulation.setScriptExecutionDisabled', { value: true })
        await sender.close()
      }
      else await sender.reload({ waitUntil: 'domcontentloaded' })
      // Allow browser scheduling overhead after the 20-second peer lease; record the actual recovery time.
      let firstLoginAt = null
      while (performance.now() - started < 30000) {
        if (await observer.locator('#access-key').count()) { firstLoginAt = performance.now() - started; break }
        assert.equal(await observer.locator('#request-goal').count(), 0)
        await pause(100)
      }
      assert.equal(await observer.locator('#request-goal').count(), 0)
      assert.ok(await clean(observer))
      const notifications = await observer.evaluate(() => window.__peerNotifications)
      const observerElapsed = await observer.evaluate(() => performance.now()) - observerStarted
      const completionObserved = notifications.some(message => !message.pending)
      assert.ok(notifications.some(message => message.pending), 'Observe the actual pending notification.')
      if (departure === 'close') {
        assert.equal(completionObserved, false, 'The close case must exercise the missing-completion lease.')
        assert.ok(observerElapsed >= 15000, 'Only the departing sender is stopped; the observer clock must advance through the deadline.')
      }
      if (baseline && (departure === 'close' || firstLoginAt === null)) {
        assert.equal(firstLoginAt, null, 'Preserve the original stuck state before fixing it.')
        assert.equal(await observer.getByRole('status').count(), 1)
      } else {
        assert.notEqual(firstLoginAt, null, 'An abandoned peer must return to an empty sign-in screen.')
        assert.ok(firstLoginAt >= 15000 || completionObserved, 'A lease must not expire before the real deadline; an actual completion notification may end it earlier.')
        assert.equal(await observer.locator('#access-key').inputValue(), '')
        assert.equal(await observer.getByRole('button', { name: 'ログイン', exact: true }).isEnabled(), true)
      }
      await observer.screenshot({ path: resolve(out, `${departure}-${firstLoginAt === null ? 'original-stuck' : 'empty-signin'}.png`), fullPage: true })
      const recovered = {}
      if (!baseline) {
        await observer.locator('#access-key').fill(key(operator))
        const accepted = observer.waitForResponse(response => new URL(response.url()).pathname === '/api/auth/login' && response.request().method() === 'POST')
        await observer.getByRole('button', { name: 'ログイン', exact: true }).click()
        const loginResponse = await accepted
        assert.equal(loginResponse.status(), 200)
        const expectedIdentity = await loginResponse.json()
        assert.ok(expectedIdentity.subject && expectedIdentity.role === 'operator')
        await observer.locator('#request-goal').waitFor()
        const identity = await observer.evaluate(async () => (await (await fetch('/api/auth/me')).json()))
        recovered.subject_matches_actual_login_response = identity.subject === expectedIdentity.subject
        recovered.role_matches_actual_login_response = identity.role === expectedIdentity.role
        assert.ok(recovered.subject_matches_actual_login_response && recovered.role_matches_actual_login_response)
        assert.equal(await observer.locator('#request-goal').inputValue(), '')
        assert.equal(await observer.locator('#request-source').inputValue(), '')
        await observer.waitForFunction(() => {
          const draft = JSON.parse(sessionStorage.getItem('agentteam.requestDraft') || 'null')
          return !draft || (!draft.goal && !draft.text && !draft.files.length)
        })
        recovered.empty_workspace_after_explicit_signin = true
      }
      report.checks.push({ id: `peer-${departure}`, status: baseline ? (firstLoginAt === null ? 'BUG_REPRODUCED' : 'ACTUAL_COMPLETION_OBSERVED') : 'PASS', actual_login_status: held.responseStatusCode, observed_ms: Math.round(performance.now() - started), observer_clock_advanced_ms: Math.round(observerElapsed), empty_signin_after_ms: firstLoginAt === null ? null : Math.round(firstLoginAt), actual_completion_notification_observed: completionObserved, prior_workspace_closed: true, private_storage_cleared: true, ...recovered })
      save()
    } finally { await context.close() }
  }
  assert.deepEqual(counts(), initial, 'This check must not create work or execution jobs.')
  report.counts_before = initial; report.counts_after = counts()
  report.additional_runs = 0; report.additional_jobs = 0; report.additional_model_calls = 0
  report.status = baseline ? 'BUG_REPRODUCED' : 'PASS'
} catch (error) {
  report.status = 'FAILED'
  report.error_name = ['Error', 'AssertionError', 'TimeoutError', 'TypeError'].includes(error?.name) ? error.name : 'Error'
  save()
  const suffix = Date.now()
  writeFileSync(resolve(out, `peer-private-failure-${suffix}.json`), JSON.stringify({ error: String(error) }, null, 2))
  if (current && !current.isClosed()) await current.screenshot({ path: resolve(out, `peer-private-failure-${suffix}.png`), timeout: 5000 })
  throw error
} finally {
  try { if (browser) await browser.close() }
  catch (error) {
    report.status = 'FAILED'; report.phase = 'browser_cleanup'
    report.error_name = ['Error', 'TimeoutError', 'TargetClosedError'].includes(error?.name) ? error.name : 'Error'
    cleanupError = error
  }
  finally { report.finished_at = new Date().toISOString(); save() }
}
if (cleanupError) throw cleanupError
console.log(JSON.stringify({ status: report.status, checks: report.checks.map(check => check.id) }))

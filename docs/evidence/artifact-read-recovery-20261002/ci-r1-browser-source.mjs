#!/usr/bin/env node
/** Actual stored artifacts, issued keys and HTTP. CDP delays/blocks traffic only. */
import { chromium } from 'playwright-core'
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { join } from 'node:path'
import { createHash } from 'node:crypto'

const cfg = JSON.parse(readFileSync(process.env.ARTIFACT_RECOVERY_CONFIG, 'utf8'))
const sha = bytes => createHash('sha256').update(bytes).digest('hex')
const specs = [
  { id: 'manual_pending', kind: 'manual', rep: 3, language: 'ja', width: 390 },
  { id: 'deadline_initial', kind: 'deadline', rep: 3, language: 'ja', width: 390 },
  { id: 'cut_initial', kind: 'cut', rep: 3, language: 'en', width: 768 },
  { id: 'loaded_copy', kind: 'loaded', rep: 3, language: 'ja', width: 390 },
]
const checkIds = ['issued_login', 'original_artifact_and_records_baseline', 'real_fault', 'pending_or_error_guard', 'native_retry', 'fresh_artifact_200', 'original_body_records_and_copy', 'old_request_cleanup', 'identity_preserved', 'read_only_boundary']
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
async function artifactBytes(page, source) {
  let digest
  await until('original artifact bytes', async () => {
    const text = await page.locator('.result-reader pre').textContent()
    digest = sha(Buffer.from(text ?? '', 'utf8'))
    return digest === source.artifact_sha256
  })
  return digest
}
const noRecordText = /この版に対する確認の記録はありません|未確認：この版の確認記録はまだありません|No checks were recorded for this version|Unverified: No check record for this version yet/
let browser, server, stopping = false
const contexts = new Set()
async function runCase(item) {
  const source = cfg.records.find(r => r.rep === item.rep), en = item.language === 'en'
  const base = `/api/runs/${source.run_id}`
  const context = await browser.newContext({ locale: en ? 'en-US' : 'ja-JP', viewport: { width: item.width, height: 900 }, reducedMotion: 'reduce' })
  contexts.add(context)
  const page = await context.newPage(); page.setDefaultTimeout(10000); page.setDefaultNavigationTimeout(15000)
  let cdp, artifactPath, mode = 'pass', phase = 'before_login', closing = false, navigating = false
  const held = [], requests = [], responses = [], failures = [], protocolErrors = [], blocked = [], pending = new Set(), requestPhases = new WeakMap(), cancelled = new Set(), networkRequests = new Map()
  const isArtifact = url => artifactPath != null && new URL(url).pathname === artifactPath
  const track = promise => { pending.add(promise); promise.catch(error => protocolErrors.push(String(error))).finally(() => pending.delete(promise)) }
  page.on('request', req => {
    requestPhases.set(req, phase)
    if (!['GET', 'HEAD', 'OPTIONS'].includes(req.method())) report.writes.push({ case: item.id, phase, method: req.method(), path: new URL(req.url()).pathname })
    if (isArtifact(req.url())) requests.push({ at: Date.now(), phase, method: req.method() })
  })
  page.on('response', res => {
    const path = new URL(res.url()).pathname
    report.http.push({ case: item.id, phase: requestPhases.get(res.request()), path, status: res.status() })
    if (isArtifact(res.url())) responses.push({ at: Date.now(), phase: requestPhases.get(res.request()), status: res.status() })
  })
  page.on('requestfailed', req => failures.push({ artifact: isArtifact(req.url()), phase: requestPhases.get(req), error: req.failure()?.errorText, closing, navigation: navigating && req.isNavigationRequest() && req.resourceType() === 'document' }))
  page.on('pageerror', error => report.errors.push({ case: item.id, error: String(error) }))
  const expectedFailure = f => f.error === 'net::ERR_ABORTED' && (f.navigation || f.closing || (f.artifact && ['held_initial', 'held_loaded'].includes(f.phase)))
    || item.kind === 'cut' && f.artifact && f.phase === 'blocked_initial' && f.error === 'net::ERR_BLOCKED_BY_CLIENT'
  const boundariesGood = () => !report.http.some(h => h.case === item.id && h.status >= 400 && !(h.path === '/api/auth/me' && h.phase === 'before_login' && h.status === 401))
    && !report.writes.some(w => w.case === item.id && !(w.phase === 'login' && w.method === 'POST' && w.path === '/api/auth/login'))
    && !failures.some(f => !expectedFailure(f)) && !protocolErrors.length && !report.errors.some(e => e.case === item.id)
  async function navigate(url) { navigating = true; try { await page.goto(url) } finally { navigating = false } }
  item.status = 'RUNNING'; save()
  try {
    await navigate(cfg.origin + '/runs')
    await page.locator('#access-key').fill(readFileSync(cfg.credentials.operator, 'utf8').trim())
    phase = 'login'
    const login = page.waitForResponse(r => new URL(r.url()).pathname === '/api/auth/login')
    await page.getByRole('button', { name: en ? 'Sign in' : 'ログイン', exact: true }).click()
    check(item, 'issued_login', (await login).status() === 200)
    await page.locator('.work-list').waitFor()
    const runResponse = await context.request.get(cfg.origin + base)
    if (runResponse.status() !== 200) throw new Error('actual_baseline_run')
    const baseline = await runResponse.json()
    const metadata = baseline.artifacts.find(a => a.logical_path === source.artifact_name && a.sha256 === source.artifact_sha256)
    if (!metadata) throw new Error('actual_artifact_missing')
    artifactPath = `/api/artifacts/${encodeURIComponent(source.run_id)}/${encodeURIComponent(metadata.artifact_id)}/versions/${metadata.revision}`
    const artifactResponse = await context.request.get(cfg.origin + artifactPath)
    const original = await artifactResponse.json()
    item.baseline = { run: baseline, artifact: original }
    const exact = target => target?.artifact_id === metadata.artifact_id && target?.revision === metadata.revision && target?.sha256 === metadata.sha256
    const checks = original.checks.filter(e => exact(e.payload.target)), reviews = original.reviews.filter(e => e.payload.target_artifacts?.some(exact))
    const expectedItems = checks.length + reviews.reduce((n, e) => n + e.payload.results.length, 0)
    item.measurements.baseline_check_count = checks.length; item.measurements.baseline_review_count = reviews.length; item.measurements.expected_record_items = expectedItems
    check(item, 'original_artifact_and_records_baseline', artifactResponse.status() === 200 && typeof original.text === 'string' && sha(Buffer.from(original.text)) === source.artifact_sha256 && checks.length > 0 && reviews.length > 0 && baseline.access.can_write)
    cdp = await context.newCDPSession(page); await cdp.send('Network.enable')
    cdp.on('Network.requestWillBeSent', e => networkRequests.set(e.requestId, { artifact: isArtifact(e.request.url), phase }))
    cdp.on('Network.loadingFailed', e => {
      if (e.canceled && e.errorText === 'net::ERR_ABORTED') cancelled.add(e.requestId)
      if (networkRequests.get(e.requestId)?.artifact && e.blockedReason && e.errorText === 'net::ERR_BLOCKED_BY_CLIENT') blocked.push({ networkId: e.requestId, reason: e.blockedReason, phase: networkRequests.get(e.requestId).phase })
    })
    cdp.on('Fetch.requestPaused', e => {
      if (mode === 'hold' && isArtifact(e.request.url) && e.request.method === 'GET' && e.responseStatusCode === 200) {
        held.push({ id: e.requestId, networkId: e.networkId, at: Date.now(), status: e.responseStatusCode, phase }); save()
      } else track(deadline('continue actual response', () => cdp.send('Fetch.continueRequest', { requestId: e.requestId }), 3000))
    })
    await cdp.send('Fetch.enable', { patterns: [{ urlPattern: cfg.origin + artifactPath + '*', requestStage: 'Response' }] })
    if (item.kind === 'cut') await cdp.send('Network.setBlockedURLs', { urls: [cfg.origin + artifactPath + '*'] })
    phase = item.kind === 'loaded' ? 'loaded_initial' : item.kind === 'cut' ? 'blocked_initial' : 'held_initial'
    mode = ['loaded', 'cut'].includes(item.kind) ? 'pass' : 'hold'
    await navigate(cfg.origin + `/runs/${source.run_id}?from=completed`)
    const state = page.locator('[data-artifact-read-state]'), retry = page.locator('[data-artifact-retry]'), adopt = page.locator('[data-adopt]'), record = page.locator('.result-record')
    let draft = null
    const draftGood = async () => item.kind !== 'loaded' || await page.getByRole('textbox', { name: '成果物のコピーを編集', exact: true }).inputValue() === draft
    const guarded = async expected => await state.getAttribute('data-artifact-read-state') === expected && await adopt.count() === 1 && await adopt.isDisabled()
      && !noRecordText.test(await page.locator('.result-checks').textContent())
    if (item.kind === 'loaded') {
      await until('initial ready', async () => await state.getAttribute('data-artifact-read-state') === 'ready')
      await artifactBytes(page, source)
      await page.locator('.result-edit-options > summary').click()
      await page.getByRole('button', { name: 'コピーを編集', exact: true }).click()
      draft = Array.from(original.text).slice(0, 1024).join('')
      item.measurements.draft_source_artifact_sha256 = sha(Buffer.from(original.text)); item.measurements.draft_excerpt_sha256 = sha(Buffer.from(draft))
      item.measurements.draft_source_codepoints = Array.from(original.text).length; item.measurements.draft_excerpt_codepoints = Array.from(draft).length
      await page.getByRole('textbox', { name: '成果物のコピーを編集', exact: true }).fill(draft)
      await deadline('tab to ready retry', () => tabTo(page, retry))
      mode = 'hold'; phase = 'held_loaded'; await page.keyboard.press('Enter')
    }
    if (item.kind === 'cut') {
      await until('real blocked artifact and error', async () => blocked.length > 0 && await state.getAttribute('data-artifact-read-state') === 'error', 10000)
      check(item, 'real_fault', blocked.every(b => b.phase === 'blocked_initial') && failures.some(f => f.artifact && f.phase === 'blocked_initial' && f.error === 'net::ERR_BLOCKED_BY_CLIENT'))
      check(item, 'pending_or_error_guard', await guarded('error'))
    } else {
      await until('real artifact 200 hold', () => held.length > 0)
      const firstHeldAt = held[0].at
      check(item, 'real_fault', held.every(h => h.status === 200))
      if (!await guarded('pending')) check(item, 'pending_or_error_guard', false)
      if (item.kind === 'loaded') {
        item.measurements.pending_body_preserved = await artifactBytes(page, source) === source.artifact_sha256 && await draftGood()
        if (!item.measurements.pending_body_preserved) check(item, 'pending_or_error_guard', false)
      }
      if (item.kind !== 'manual') {
        await delay(Math.max(0, 12000 - (Date.now() - firstHeldAt)))
        item.measurements.predeadline_observed_after_hold_ms = Date.now() - firstHeldAt
        if (!await guarded('pending') || !await draftGood()) check(item, 'pending_or_error_guard', false)
        await until('artifact deadline error', async () => await state.getAttribute('data-artifact-read-state') === 'error', Math.max(1, 22000 - (Date.now() - firstHeldAt)))
        item.measurements.deadline_error_after_hold_ms = Date.now() - firstHeldAt
        if (item.kind === 'loaded') item.measurements.error_body_preserved = await artifactBytes(page, source) === source.artifact_sha256 && await draftGood()
        check(item, 'pending_or_error_guard', item.measurements.deadline_error_after_hold_ms <= 22000 && await guarded('error') && (item.kind !== 'loaded' || item.measurements.error_body_preserved))
      } else check(item, 'pending_or_error_guard', await guarded('pending'))
    }
    await deadline('natural tab to retry', () => tabTo(page, retry))
    if (item.kind === 'cut') await cdp.send('Network.setBlockedURLs', { urls: [] })
    mode = 'pass'; phase = 'explicit_retry'; const pressAt = Date.now()
    await page.keyboard.press('Enter')
    item.measurements.enter_after_initial_request_ms = pressAt - requests[0].at
    check(item, 'native_retry', item.kind !== 'manual' || item.measurements.enter_after_initial_request_ms < 2000)
    await until('fresh actual artifact 200', () => requests.some(x => x.phase === 'explicit_retry' && x.at >= pressAt) && responses.some(x => x.phase === 'explicit_retry' && x.status === 200), 3000)
    item.measurements.recovery_after_enter_ms = Date.now() - pressAt
    check(item, 'fresh_artifact_200', true)
    await until('artifact ready', async () => await state.getAttribute('data-artifact-read-state') === 'ready')
    item.measurements.artifact_sha256 = await artifactBytes(page, source)
    // Observe focus after React layout and its scroll correction, before any
    // further click changes focus. Do not repair or focus the element here.
    await deadline('settled retry layout', () => page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))), 5000)
    item.measurements.retry_geometry = await retry.evaluate(el => {
      const rect = el.getBoundingClientRect(), menu = document.querySelector('.top.side')?.getBoundingClientRect()
      const overlap = !!menu && menu.right > rect.left && menu.left < rect.right && menu.bottom > rect.top && menu.top < rect.bottom
      const hit = document.elementFromPoint((rect.left + rect.right) / 2, (rect.top + rect.bottom) / 2)
      return { top: rect.top, bottom: rect.bottom, left: rect.left, right: rect.right, viewport_height: innerHeight, viewport_width: innerWidth,
        header_bottom: menu?.bottom ?? 0, focused: document.activeElement === el, header_overlap: overlap,
        hit_is_target: hit === el || !!hit && el.contains(hit), visible: rect.top >= 0 && rect.bottom <= innerHeight && rect.left >= 0 && rect.right <= innerWidth && !overlap }
    })
    const geometry = item.measurements.retry_geometry
    check(item, 'native_retry', geometry.focused && geometry.visible && geometry.hit_is_target)
    if (!await record.evaluate(el => el.open)) await record.locator(':scope > summary').click()
    item.measurements.rendered_record_items = await record.locator('.check-record > li').count()
    item.measurements.draft_preserved = item.kind === 'loaded' ? await draftGood() : null
    check(item, 'original_body_records_and_copy', item.measurements.artifact_sha256 === source.artifact_sha256 && item.measurements.rendered_record_items === expectedItems && !noRecordText.test(await record.textContent()) && !await adopt.isDisabled() && await draftGood())
    if (held.length) {
      await until('held requests cancelled by app', () => held.every(h => h.networkId && cancelled.has(h.networkId)), 5000)
      for (const h of held) {
        try { await deadline('release old response', () => cdp.send('Fetch.continueRequest', { requestId: h.id }), 3000); h.release = 'continued' }
        catch (error) {
          if (!cancelled.has(h.networkId) || !/Invalid (?:InterceptionId|interceptionId)|Invalid requestId|No resource with given identifier|Could not find request/.test(String(error))) throw error
          h.release = 'already_cancelled'
        }
      }
    }
    item.measurements.old_cancelled_count = held.filter(h => cancelled.has(h.networkId)).length
    item.measurements.held_200_count = held.length; item.measurements.blocked_artifact_count = blocked.length
    check(item, 'old_request_cleanup', held.every(h => h.release) && (item.kind !== 'cut' || blocked.length > 0))
    await delay(300)
    const finalResponse = await context.request.get(cfg.origin + base), finalArtifactResponse = await context.request.get(cfg.origin + artifactPath)
    const final = await finalResponse.json(), finalArtifact = await finalArtifactResponse.json()
    item.final = { run: final, artifact: finalArtifact }
    const identity = finalResponse.status() === 200 && finalArtifactResponse.status() === 200 && final.run_id === baseline.run_id && final.status === baseline.status && final.last_seq === baseline.last_seq
      && JSON.stringify(finalArtifact) === JSON.stringify(original) && new URL(page.url()).pathname === `/runs/${source.run_id}`
    item.measurements.identity_status_last_seq_preserved = identity
    check(item, 'identity_preserved', identity && await artifactBytes(page, source) === source.artifact_sha256 && await draftGood())
    item.measurements.expected_abort_count = failures.filter(f => f.artifact && f.error === 'net::ERR_ABORTED' && ['held_initial', 'held_loaded'].includes(f.phase)).length
    check(item, 'read_only_boundary', boundariesGood()); item.status = 'PASS'
  } catch (error) { item.status = 'FAIL'; item.error_type = error.name; item.error = String(error); save() }
  finally {
    item.held = held; item.blocked = blocked; item.requests = requests; item.responses = responses; item.failures = failures; item.protocol_errors = protocolErrors
    closing = true
    if (cdp) {
      await clean(item.id + '-unblock', () => cdp.send('Network.setBlockedURLs', { urls: [] }))
      await clean(item.id + '-fetch-disable', () => cdp.send('Fetch.disable'))
    }
    await clean(item.id + '-pending-cdp', () => Promise.allSettled([...pending]))
    await clean(item.id + '-context', () => context.close()); contexts.delete(context)
    if (!boundariesGood()) { item.status = 'FAIL'; Object.assign(item.checks.find(x => x.id === 'read_only_boundary'), { status: 'FAIL' }) }
    if (report.cleanup.some(c => c.id.startsWith(item.id + '-') && c.status !== 'PASS')) item.status = 'FAIL'
    save()
  }
}
try {
  const url = new URL(cfg.origin)
  if (url.protocol !== 'http:' || url.hostname !== '127.0.0.1') throw new Error('loopback_only')
  await deadline('whole artifact recovery suite', async () => {
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

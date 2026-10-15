#!/usr/bin/env node
/** Read-only audit of the real static site; no response, API, clipboard or data mocks.
 * node frontend/scripts/site-quality-audit.mjs --url http://127.0.0.1:8897/ --out /absolute/new/evidence
 * SITE_URL / OUT / CHROME_PATH / HEADED=1 are optional alternatives. A new OUT is required.
 * Opens only loopback pages. Activates fragment links, existing finding buttons, FAQ and copy;
 * never fills/submits a form, follows external links, executes the copied command, or calls a model.
 * Inspection scripts and CSS scaling below are measurement instrumentation, not production changes.
 * Results are automated observations, not award recognition, WCAG certification, or human acceptance.
 */
import { chromium } from 'playwright-core'
import AxeBuilder from '@axe-core/playwright'
import { mkdirSync, existsSync, readFileSync, writeFileSync } from 'node:fs'
import { resolve, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createHash } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { createRequire } from 'node:module'
import os from 'node:os'

const args = process.argv.slice(2)
const option = (name, fallback) => {
  const i = args.indexOf(name)
  if (i < 0) return fallback
  if (!args[i + 1] || args[i + 1].startsWith('--')) throw new Error(`${name} requires a value`)
  return args[i + 1]
}
if (args.includes('--help')) {
  console.log('Usage: node frontend/scripts/site-quality-audit.mjs --url http://127.0.0.1:8897/ --out /absolute/new/evidence\nEnvironment: SITE_URL, OUT, CHROME_PATH, HEADED=1. No server or model is started.')
  process.exit(0)
}
for (let i = 0; i < args.length; i += 2) if (!['--url', '--out'].includes(args[i])) throw new Error(`Unknown option ${args[i]}`)
const base = new URL(option('--url', process.env.SITE_URL || 'http://127.0.0.1:8897/'))
if (!['127.0.0.1', 'localhost', '[::1]'].includes(base.hostname) || !['http:', 'https:'].includes(base.protocol) || base.username || base.password || base.search || base.hash) throw new Error('Use an uncredentialed loopback base URL without query/fragment.')
if (!base.pathname.endsWith('/')) base.pathname += '/'
const output = option('--out', process.env.OUT)
if (!output) throw new Error('Provide --out or OUT; evidence must not overwrite an earlier run.')
const out = resolve(output)
if (existsSync(join(out, 'audit.json'))) throw new Error('OUT already has audit.json; choose a new evidence directory.')
mkdirSync(out, { recursive: true, mode: 0o700 })
const repo = fileURLToPath(new URL('../../', import.meta.url))
const require = createRequire(import.meta.url)
const sha = data => createHash('sha256').update(data).digest('hex')
const save = (name, data) => writeFileSync(join(out, name), JSON.stringify(data, null, 2) + '\n', { mode: 0o600 })
const git = argv => { try { return execFileSync('git', argv, { cwd: repo, encoding: 'utf8' }).trim() } catch { return null } }
const sourceState = () => ({ commit: git(['rev-parse', 'HEAD']), status: git(['status', '--short']), files: Object.fromEntries(['docs/index.html', 'docs/ja/index.html', 'docs/home.css', 'docs/home.js', 'docs/portfolio.js', 'docs/site/build_site.py', 'docs/site/copy.json'].filter(p => existsSync(join(repo, p))).map(p => [p, sha(readFileSync(join(repo, p)))])) })
// Never retain query values, credentials, response headers, request bodies, or clipboard plaintext.
const safeURL = value => { try { const u = new URL(value, base); return `${u.origin}${u.pathname}${u.search ? '?[redacted]' : ''}` } catch { return '[invalid URL]' } }
const safeText = value => String(value).replace(/https?:\/\/[^\s"'<>]+/g, safeURL).replace(/(?:Bearer\s+|(?:api[_-]?key|token|authorization)\s*[:=]\s*)\S+/gi, '[redacted credential]').slice(0, 1200)
const report = {
  schema_version: 1, started_at: new Date().toISOString(), base_url: base.href, output: out,
  purpose: 'Real static-site layout, keyboard, progressive enhancement, motion and accessibility regression evidence',
  environment: { platform: process.platform, architecture: process.arch, os_release: os.release(), node: process.version, playwright: require('playwright-core/package.json').version, axe: JSON.parse(readFileSync(new URL('../node_modules/@axe-core/playwright/package.json', import.meta.url), 'utf8')).version, headless: process.env.HEADED !== '1', device_scale_factor: 1, hardware_concurrency: os.availableParallelism(), network_throttling: 'none', cpu_throttling: 'none', cache: 'fresh context + Chrome Network.setCacheDisabled', initial_observation_ms_after_load: 1500 },
  script_sha256: sha(readFileSync(fileURLToPath(import.meta.url))), source_before: sourceState(), checks: [], cases: [], resources: [], human_acceptance: false, award_certification: false,
  limitations: [
    'Localhost, one installed desktop Chrome and unthrottled host; narrow viewports are not physical mobile-device tests.',
    'One initial navigation sample per case; LCP/CLS are bounded lab observations, not field p75, INP, or a performance guarantee.',
    '720 CSS-pixel viewport represents the reflow width of 1440 at 200%; CSS html zoom and precomputed element-font scaling are additional stress conditions, not browser-menu or OS zoom.',
    'Axe does not establish WCAG conformance. Focus styling is recorded, not judged perceptually; screen-reader and human first-use assessment remain unperformed.',
    'No external link availability, form delivery, installation command, backend workflow, LLM quality, or award submission is tested.',
    'Clipboard comparison covers the copied public command only. No prior clipboard contents are read or saved.',
    'Rendered DOM, computed styles, screenshots and content hashes do not prove the truth of marketing claims or provenance of the published records.',
  ],
}
const record = (scope, id, ok, expected, observed) => report.checks.push({ scope, id, status: ok === null ? 'UNVERIFIED' : ok ? 'PASS' : 'FAIL', expected, observed })
writeFileSync(join(out, 'runner-source.mjs'), readFileSync(fileURLToPath(import.meta.url)), { mode: 0o600 })
const resources = new Map()
let browser

function performanceObservers() {
  const metrics = { lcp: null, cls: 0, shifts: [], supported: PerformanceObserver.supportedEntryTypes || [] }
  window.__siteAuditMetrics = metrics
  if (metrics.supported.includes('largest-contentful-paint')) new PerformanceObserver(list => {
    for (const e of list.getEntries()) metrics.lcp = { start_time_ms: e.startTime, size: e.size, tag: e.element?.tagName || null }
  }).observe({ type: 'largest-contentful-paint', buffered: true })
  let first = 0, last = 0, session = 0
  if (metrics.supported.includes('layout-shift')) new PerformanceObserver(list => {
    for (const e of list.getEntries()) {
      if (e.hadRecentInput) continue
      if (!last || e.startTime - last > 1000 || e.startTime - first > 5000) { first = e.startTime; session = 0 }
      last = e.startTime; session += e.value; metrics.cls = Math.max(metrics.cls, session)
      metrics.shifts.push({ start_time_ms: e.startTime, value: e.value })
    }
  }).observe({ type: 'layout-shift', buffered: true })
}

async function inspectLayout(page) {
  return page.evaluate(() => {
    const root = document.documentElement, w = root.clientWidth
    const label = e => ({ tag: e.tagName, id: e.id || null, text: (e.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 90) })
    const overflow = [...document.querySelectorAll('main *, header *, footer *')].flatMap(e => {
      const r = e.getBoundingClientRect(), s = getComputedStyle(e)
      if (!r.width || !r.height || s.visibility === 'hidden' || s.display === 'none' || e.closest('[hidden]')) return []
      // Intentionally offscreen, aria-hidden anti-spam fields are not visible overflow.
      // The independent root/body scroll-width check still catches document expansion.
      if (e.closest('[aria-hidden="true"]') && (r.right <= 0 || r.left >= innerWidth)) return []
      return r.left < -1 || r.right > innerWidth + 1 ? [{ ...label(e), left: r.left, right: r.right, width: r.width }] : []
    }).slice(0, 35)
    return { viewport: { width: innerWidth, height: innerHeight, visual_width: visualViewport?.width, visual_scale: visualViewport?.scale }, client_width: w, scroll_width: root.scrollWidth, body_scroll_width: document.body.scrollWidth, html_zoom: getComputedStyle(root).zoom, html_font_px: getComputedStyle(root).fontSize, body_font_px: getComputedStyle(document.body).fontSize, h1_font_px: document.querySelector('h1') ? getComputedStyle(document.querySelector('h1')).fontSize : null, overflow }
  })
}

async function tabTo(page, target) {
  if (await target.count() !== 1 || !await target.isVisible()) throw new Error('Keyboard target is absent, ambiguous, or hidden')
  const max = Math.max(40, await page.locator('a,button,input,textarea,select,summary,[tabindex]').count() * 2 + 10)
  for (let i = 0; i <= max; i++) {
    if (await target.evaluate(e => e === document.activeElement)) return { tab_presses: i, focus: await target.evaluate(e => {
      const s = getComputedStyle(e), r = e.getBoundingClientRect()
      return { name: e.getAttribute('aria-label') || e.textContent.trim().slice(0, 120), tag: e.tagName, outline_style: s.outlineStyle, outline_width: s.outlineWidth, outline_color: s.outlineColor, box_shadow: s.boxShadow, left: r.left, top: r.top, right: r.right, bottom: r.bottom, in_viewport: r.top >= 0 && r.bottom <= innerHeight && r.left >= 0 && r.right <= innerWidth }
    }) }
    await page.keyboard.press('Tab')
  }
  throw new Error('Target could not be reached by sequential Tab navigation')
}

async function keyboardChecks(page, scope, context) {
  const step = async (id, fn) => { try { await fn() } catch (e) { record(scope, id, false, 'Real keyboard action completes', safeText(e.message)) } }
  await step('keyboard-cta', async () => {
    const outcomes = []
    for (const href of ['#proof', '#start']) {
      // Destination is a stable semantic contract; wording can improve without changing this test.
      const target = page.getByRole('main').getByRole('link').and(page.locator(`a[href="${href}"]`)).filter({ visible: true }).first()
      const focus = await tabTo(page, target)
      await page.keyboard.press('Enter')
      await page.waitForFunction(hash => location.hash === hash, href)
      const found = await page.evaluate(hash => !!document.getElementById(decodeURIComponent(hash.slice(1))), href)
      outcomes.push({ href, found, ...focus })
    }
    record(scope, 'keyboard-cta', outcomes.every(o => o.found), 'Enter on Tab-reachable record and installation links opens real same-page destinations', outcomes)
  })
  await step('keyboard-findings', async () => {
    const buttons = page.getByRole('button').and(page.locator('[data-finding]'))
    if (!await buttons.count()) throw new Error('No real-record selection buttons')
    const selections = []
    for (let i = 0; i < await buttons.count(); i++) {
      const button = buttons.nth(i), id = await button.getAttribute('data-finding'), focus = await tabTo(page, button)
      await page.keyboard.press(i % 2 ? 'Space' : 'Enter')
      const state = await page.evaluate(() => ({ pressed: [...document.querySelectorAll('[data-finding][aria-pressed="true"]')].map(e => e.dataset.finding), visible: [...document.querySelectorAll('[data-diff]')].filter(e => !e.hidden && e.getBoundingClientRect().height > 0).map(e => ({ id: e.dataset.diff, characters: e.textContent.trim().length })) }))
      selections.push({ id, focus, ...state })
    }
    record(scope, 'keyboard-findings', selections.every(s => s.pressed.length === 1 && s.pressed[0] === s.id && s.visible.length === 1 && s.visible[0].id === s.id && s.visible[0].characters > 0), 'Each actual finding selects exactly its recorded diff with Enter/Space', selections)
  })
  await step('keyboard-faq', async () => {
    const summaries = page.locator('main details > summary')
    if (!await summaries.count()) throw new Error('No semantic FAQ disclosure')
    const outcomes = []
    for (let i = 0; i < await summaries.count(); i++) {
      const summary = summaries.nth(i), focus = await tabTo(page, summary)
      const before = await summary.evaluate(e => e.parentElement.open)
      await page.keyboard.press('Enter')
      const opened = await summary.evaluate(e => ({ open: e.parentElement.open, answer_characters: [...e.parentElement.children].filter(c => c !== e).map(c => c.textContent.trim()).join('').length }))
      await page.keyboard.press('Space')
      const restored = await summary.evaluate(e => e.parentElement.open)
      outcomes.push({ focus, before, ...opened, restored })
    }
    record(scope, 'keyboard-faq', outcomes.every(o => o.open !== o.before && o.restored === o.before && o.answer_characters > 0), 'Native disclosures toggle and restore with keyboard; actual answers exist', outcomes)
  })
  await step('keyboard-copy', async () => {
    const button = page.getByRole('button', { name: /^(コピー|Copy)$/i })
    const command = await page.locator('main code').allTextContents()
    const expected = command.find(t => t.includes('agentteam quickstart'))
    if (!expected) throw new Error('The displayed real installation command was not found')
    try { await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: base.origin }) }
    catch (e) { record(scope, 'keyboard-copy', null, 'Real clipboard capability is available for byte comparison', safeText(e.message)); return }
    if (!await page.evaluate(() => !!navigator.clipboard?.readText)) { record(scope, 'keyboard-copy', null, 'Real Clipboard API is available', 'Installed browser context has no clipboard read capability'); return }
    const focus = await tabTo(page, button)
    await page.keyboard.press('Enter')
    await page.waitForFunction(() => [...document.querySelectorAll('button,[role="status"]')].some(e => /^(コピーしました|Copied)$/i.test(e.textContent.trim())))
    let actual
    try { actual = await page.evaluate(() => navigator.clipboard.readText()) }
    catch (e) { record(scope, 'keyboard-copy', null, 'Real copied bytes can be read after the keyboard action', safeText(e.message)); return }
    record(scope, 'keyboard-copy', actual === expected, 'Real clipboard bytes equal the displayed command; command is not executed', { ...focus, copied_sha256: sha(actual), displayed_sha256: sha(expected), byte_length: Buffer.byteLength(actual) })
  })
}

async function runCase(lang, mode, width, height) {
  const scope = `${lang}-${mode}-${width}`, url = new URL(lang === 'ja' ? 'ja/' : './', base).href
  const context = await browser.newContext({ locale: lang === 'ja' ? 'ja-JP' : 'en-US', viewport: { width, height }, deviceScaleFactor: 1, javaScriptEnabled: mode !== 'no-js', reducedMotion: mode === 'reduced-motion' ? 'reduce' : 'no-preference' })
  const page = await context.newPage()
  page.setDefaultTimeout(7000)
  page.setDefaultNavigationTimeout(20000)
  const item = { scope, url, mode, width, height, javascript: mode !== 'no-js', console_errors: [], page_errors: [], failed_requests: [], http_errors: [], non_read_requests: [], screenshots: [], requests: 0, resource_hash_failures: [] }
  report.cases.push(item)
  const pending = []
  page.on('console', m => { if (m.type() === 'error') item.console_errors.push(safeText(m.text())) })
  page.on('pageerror', e => item.page_errors.push(safeText(e.message)))
  page.on('request', req => { item.requests++; if (!['GET', 'HEAD', 'OPTIONS'].includes(req.method())) item.non_read_requests.push({ method: req.method(), url: safeURL(req.url()) }) })
  page.on('requestfailed', req => item.failed_requests.push({ url: safeURL(req.url()), reason: safeText(req.failure()?.errorText || 'unknown'), type: req.resourceType() }))
  page.on('response', response => {
    const req = response.request(), type = req.resourceType(), url = safeURL(response.url())
    if (response.status() >= 400) item.http_errors.push({ url, status: response.status(), type })
    if (new URL(response.url()).origin === base.origin && ['document', 'stylesheet', 'script', 'image', 'font'].includes(type)) pending.push((async () => {
      try {
        const body = await response.body(), digest = sha(body), key = `${url}|${digest}`
        if (!resources.has(key)) { resources.set(key, { url, type, sha256: digest, bytes: body.length, scopes: [] }); writeFileSync(join(out, `${digest}.${type === 'document' ? 'html' : type === 'stylesheet' ? 'css' : type === 'script' ? 'js' : `${type}.bin`}`), body, { mode: 0o600 }) }
        resources.get(key).scopes.push(scope)
      } catch (e) { item.resource_hash_failures.push({ url, error: safeText(e.message) }) }
    })())
  })
  const shot = async label => { const path = join(out, `${scope}-${label}.png`); await page.screenshot({ path, fullPage: label === 'full', timeout: 15000 }); item.screenshots.push(path) }
  try {
    await page.addInitScript(performanceObservers)
    const cdp = await context.newCDPSession(page)
    await cdp.send('Network.enable')
    await cdp.send('Network.setCacheDisabled', { cacheDisabled: true })
    const response = await page.goto(url, { waitUntil: 'load' })
    record(scope, 'http-document', response?.status() === 200, 'Real document responds HTTP 200', response?.status())
    await page.evaluate(() => document.fonts.ready)
    await page.waitForTimeout(1500)
    item.initial_lab = await page.evaluate(() => {
      const n = performance.getEntriesByType('navigation')[0], entries = performance.getEntriesByType('resource')
      return { observed_at_ms: performance.now(), navigation: n?.toJSON(), lcp: window.__siteAuditMetrics?.lcp ?? null, cls_max_session_window: window.__siteAuditMetrics?.cls ?? null, layout_shifts: window.__siteAuditMetrics?.shifts || [], observers_supported: window.__siteAuditMetrics?.supported || [], resources: entries.map(e => ({ name: e.name, type: e.initiatorType, start_time_ms: e.startTime, duration_ms: e.duration, transfer_bytes: e.transferSize, encoded_bytes: e.encodedBodySize, decoded_bytes: e.decodedBodySize })), transfer_bytes_including_document: (n?.transferSize || 0) + entries.reduce((sum, e) => sum + e.transferSize, 0), byte_measurement: 'Resource Timing transferSize; zero can mean cached or unavailable cross-origin timing. Media is not played.' }
    })
    if (item.initial_lab.navigation) item.initial_lab.navigation.name = safeURL(item.initial_lab.navigation.name)
    item.initial_lab.resources.forEach(r => { r.name = safeURL(r.name) })
    if (mode !== 'normal') item.initial_lab.comparison_note = 'Context or layout stress differs from ordinary navigation; do not combine into a field metric.'
    item.layout_before_scaling = await inspectLayout(page)
    if (mode === 'reflow-html') await page.evaluate(() => { document.documentElement.style.zoom = '2' })
    if (mode === 'reflow-text') item.scaled_element_count = await page.evaluate(() => {
      // Read every computed value first: inherited sizes must not compound while applying the stress.
      const sizes = [...document.querySelectorAll('html,body,body *')].filter(e => e instanceof HTMLElement).map(e => [e, parseFloat(getComputedStyle(e).fontSize)])
      for (const [e, size] of sizes) if (Number.isFinite(size)) e.style.fontSize = `${size * 2}px`
      return sizes.length
    })
    item.scaling = { method: mode === 'reflow-html' ? '720 viewport + html CSS zoom:2 (additional stress)' : mode === 'reflow-text' ? '720 viewport + every precomputed HTML element font-size ×2; fixed line-heights unchanged (additional stress)' : mode === 'reflow-720' ? '720 CSS px = half of 1440; layout reflow proxy, no actual browser zoom' : 'none' }
    await shot('fold')
    // Scroll the real document to reveal lazy content; no forced opacity, hidden flags, or animation removal.
    item.scroll_samples = []
    const documentHeight = await page.evaluate(() => document.documentElement.scrollHeight)
    for (let y = 0; y <= Math.min(documentHeight, 40000); y += Math.max(300, height * .8)) {
      await page.evaluate(y => window.scrollTo(0, y), y)
      await page.waitForTimeout(75)
      item.scroll_samples.push(await inspectLayout(page))
    }
    item.layout = await inspectLayout(page)
    item.images = await page.locator('img').evaluateAll(async images => {
      const visible = images.filter(e => e.getBoundingClientRect().width > 0 && !e.closest('[hidden]'))
      await Promise.all(visible.map(e => Promise.race([e.decode().catch(() => {}), new Promise(resolve => setTimeout(resolve, 5000))])))
      return visible.map(e => ({ source: e.currentSrc, alt: e.alt, complete: e.complete, natural_width: e.naturalWidth, natural_height: e.naturalHeight }))
    })
    item.images.forEach(i => { i.source = safeURL(i.source) })
    record(scope, 'loaded-images', item.images.every(i => i.complete && i.natural_width > 0), 'Rendered image resources decode successfully after scrolling; no substitute pixels', item.images)
    item.form = await page.evaluate(() => {
      const form = document.querySelector('#portfolio-form'), fieldset = form?.querySelector('fieldset'), copy = document.querySelector('#copy')
      return { present: !!form, fieldset_present: !!fieldset, fieldset_disabled: fieldset?.disabled ?? null, controls: [...(form?.querySelectorAll('input,textarea,select,button') || [])].map(e => ({ tag: e.tagName, type: e.type, disabled: e.matches(':disabled') })), copy_present: !!copy, copy_hidden: !copy || copy.hidden || !copy.getBoundingClientRect().height || getComputedStyle(copy).display === 'none', no_js_notice: form?.querySelector('noscript')?.textContent.trim().length > 0 }
    })
    record(scope, 'form-progressive-enhancement', mode === 'no-js' ? item.form.fieldset_disabled === true && item.form.controls.length > 0 && item.form.controls.every(c => c.disabled) && item.form.no_js_notice && item.form.copy_present && item.form.copy_hidden : item.form.fieldset_disabled === false && item.form.controls.length > 0 && item.form.controls.every(c => !c.disabled), mode === 'no-js' ? 'No-JS form controls are effectively disabled by fieldset with an explanation; unsupported copy control is hidden' : 'Real JS initializes and enables form controls; no input or submit is performed', item.form)
    if (width <= 390) {
      item.mobile_header = await page.evaluate(() => ['#proof', '#app', '#start'].map(href => {
        const e = document.querySelector(`header nav a[href="${href}"]`), r = e?.getBoundingClientRect(), s = e && getComputedStyle(e)
        return { href, present: !!e, visible: !!r && r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden', within_width: !!r && r.left >= 0 && r.right <= innerWidth, label: e?.textContent.trim() }
      }))
      record(scope, 'mobile-header-navigation', item.mobile_header.every(n => n.visible && n.within_width), 'Record, usage and installation links remain visible in the narrow header', item.mobile_header)
      item.mobile_picture = await page.evaluate(() => {
        const img = document.querySelector('main picture img'), figure = img?.closest('figure')
        return { present: !!img, current_src: img?.currentSrc || null, natural_width: img?.naturalWidth || 0, matching_sources: [...(img?.parentElement.querySelectorAll('source[media]') || [])].filter(s => matchMedia(s.media).matches).map(s => s.srcset), full_size_links: [...(figure?.querySelectorAll('a[href]') || [])].filter(e => e.getBoundingClientRect().width > 0 && e.getBoundingClientRect().height > 0 && getComputedStyle(e).visibility !== 'hidden').map(e => ({ href: e.href, label: e.textContent.trim() })) }
      })
      const originalSrc = item.mobile_picture.current_src
      const visibleOriginalLink = item.mobile_picture.full_size_links.some(a => a.href === originalSrc)
      item.mobile_picture.current_src = originalSrc && safeURL(originalSrc)
      item.mobile_picture.full_size_links.forEach(a => { a.href = safeURL(a.href) })
      record(scope, 'mobile-picture-and-original', item.mobile_picture.present && /mobile/i.test(originalSrc || '') && item.mobile_picture.natural_width > 0 && item.mobile_picture.natural_width <= 768 && item.mobile_picture.matching_sources.length > 0 && visibleOriginalLink, 'Narrow screen selects a loaded mobile image and exposes its same-byte original link; external navigation is not activated', item.mobile_picture)
    }
    item.after_scroll_resource_timing = await page.evaluate(() => {
      const n = performance.getEntriesByType('navigation')[0], entries = performance.getEntriesByType('resource')
      return { observed_at_ms: performance.now(), resource_count: entries.length, transfer_bytes_including_document: (n?.transferSize || 0) + entries.reduce((sum, e) => sum + e.transferSize, 0), encoded_resource_bytes: entries.reduce((sum, e) => sum + e.encodedBodySize, 0), limitation: 'After scrolling and image decode; unplayed media is excluded and zero cross-origin timing may be unavailable.' }
    })
    record(scope, 'horizontal-overflow', item.scroll_samples.every(s => s.scroll_width <= s.viewport.width + 1 && s.body_scroll_width <= s.viewport.width + 1 && s.overflow.length === 0), 'No document or visible element extends horizontally at any sampled scroll position', item.scroll_samples.filter(s => s.scroll_width > s.viewport.width + 1 || s.body_scroll_width > s.viewport.width + 1 || s.overflow.length).slice(0, 4))
    const content = await page.evaluate(() => ({ lang: document.documentElement.lang, title: document.title, h1: [...document.querySelectorAll('h1')].map(e => e.innerText), main_characters: document.querySelector('main')?.innerText.trim().length || 0, evidence_links: [...document.querySelectorAll('main a[href]')].filter(e => /\/evidence\//.test(e.href)).length, command_visible: [...document.querySelectorAll('main code')].some(e => /agentteam quickstart/.test(e.textContent) && e.getBoundingClientRect().height > 0), findings: [...document.querySelectorAll('[data-diff]')].map(e => ({ id: e.dataset.diff, visible: !e.hidden && e.getBoundingClientRect().height > 0 && getComputedStyle(e).opacity !== '0', characters: e.textContent.trim().length })), invisible_content: [...document.querySelectorAll('main h1,main h2,main p,[data-reveal]')].filter(e => !e.closest('[hidden],details:not([open])') && getComputedStyle(e).opacity === '0').map(e => e.tagName + (e.id ? '#' + e.id : '')).slice(0, 30) }))
    item.content = content
    record(scope, 'language-and-main', content.lang.split('-')[0] === lang && content.h1.length === 1 && content.main_characters > 0, 'Matching HTML language, one substantive main heading and readable main content', content)
    if (mode === 'no-js') record(scope, 'no-js-content', content.command_visible && content.evidence_links > 0 && content.findings.length > 0 && content.findings.every(f => f.visible && f.characters > 0) && content.invisible_content.length === 0, 'Main text, every published recorded diff and installation command remain readable with site JavaScript disabled', content)
    if (mode === 'reduced-motion') {
      item.motion = await page.evaluate(() => ({ matches: matchMedia('(prefers-reduced-motion: reduce)').matches, running_animations: document.getAnimations().filter(a => a.playState === 'running').map(a => ({ type: a.constructor.name, duration: a.effect?.getComputedTiming().duration, iterations: a.effect?.getComputedTiming().iterations })), media: [...document.querySelectorAll('video,audio')].map(e => ({ tag: e.tagName, paused: e.paused, time: e.currentTime, autoplay: e.autoplay })) }))
      record(scope, 'reduced-motion', item.motion.matches && item.motion.running_animations.length === 0 && item.motion.media.every(m => m.paused && !m.autoplay) && content.invisible_content.length === 0, 'Reduced motion disables running decorative animation and automatic media while exposing content', item.motion)
    }
    if (mode === 'normal' && [390, 1440].includes(width) || mode.startsWith('reflow')) {
      const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']).analyze()
      item.axe = { version: result.testEngine.version, violations: result.violations.map(v => ({ id: v.id, impact: v.impact, help: v.help, help_url: v.helpUrl, nodes: v.nodes.map(n => ({ target: n.target, summary: n.failureSummary })) })), incomplete: result.incomplete.map(v => ({ id: v.id, impact: v.impact, help: v.help, targets: v.nodes.map(n => n.target) })), passes: result.passes.map(v => v.id) }
      record(scope, 'axe', item.axe.violations.length === 0, 'No automated WCAG A/AA violations; incomplete findings require separate review', { violations: item.axe.violations, incomplete_count: item.axe.incomplete.length })
    }
    await page.evaluate(() => window.scrollTo(0, 0))
    await shot('full')
    if (mode === 'normal' && width === 1440) { await keyboardChecks(page, scope, context); await shot('keyboard') }
  } catch (e) {
    item.error = safeText(e.message)
    record(scope, 'case-completed', false, 'All scheduled checks complete', item.error)
    try { await shot('error') } catch { /* Preserve other evidence even if Chrome has gone away. */ }
  } finally {
    await Promise.allSettled(pending)
    record(scope, 'console-network', !item.console_errors.length && !item.page_errors.length && !item.failed_requests.length && !item.http_errors.length, 'No console, page, failed-request or HTTP error observed', { console: item.console_errors, page: item.page_errors, requests: item.failed_requests, http: item.http_errors })
    record(scope, 'no-write-requests', item.non_read_requests.length === 0, 'No non-read HTTP request observed during inspection', item.non_read_requests)
    record(scope, 'source-capture', item.resource_hash_failures.length === 0, 'All fetched local HTML/CSS/JS/image/font bytes are retained with SHA-256; media is not played', item.resource_hash_failures)
    await context.close()
    save(`${scope}.json`, item)
    report.resources = [...resources.values()]
    save('audit.json', report)
  }
}

try {
  browser = await chromium.launch({ ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : { channel: 'chrome' }), headless: process.env.HEADED !== '1' })
  report.environment.chrome = browser.version()
  for (const lang of ['ja', 'en']) {
    for (const width of [1440, 390, 320, 768]) await runCase(lang, 'normal', width, width < 768 ? 844 : 1000)
    for (const mode of ['reflow-720', 'reflow-html', 'reflow-text']) await runCase(lang, mode, 720, 1000)
    await runCase(lang, 'no-js', 390, 844)
    await runCase(lang, 'reduced-motion', 390, 844)
  }
} catch (e) {
  record('audit', 'runner-completed', false, 'Installed real Chrome completes the audit', safeText(e.message))
} finally {
  if (browser) await browser.close()
  report.source_after = sourceState()
  const changed = Object.keys(report.source_before.files).filter(p => report.source_before.files[p] !== report.source_after.files[p])
  const variants = new Map()
  for (const r of resources.values()) { if (!variants.has(r.url)) variants.set(r.url, new Set()); variants.get(r.url).add(r.sha256) }
  const mixed = [...variants].filter(([, hashes]) => hashes.size > 1).map(([url]) => url)
  record('audit', 'stable-source', !changed.length && !mixed.length && report.source_before.commit === report.source_after.commit, 'One consistent code/page revision throughout; edited sources invalidate comparisons', { changed_files: changed, multiple_byte_versions: mixed, commit_changed: report.source_before.commit !== report.source_after.commit })
  report.finished_at = new Date().toISOString()
  report.summary = { cases: report.cases.length, passed: report.checks.filter(c => c.status === 'PASS').length, failed: report.checks.filter(c => c.status === 'FAIL').length, unverified: report.checks.filter(c => c.status === 'UNVERIFIED').length, stable_source: !changed.length && !mixed.length && report.source_before.commit === report.source_after.commit, human_acceptance: false, award_certification: false }
  report.resources = [...resources.values()]
  save('audit.json', report)
  console.log(JSON.stringify({ report: join(out, 'audit.json'), ...report.summary, failures: report.checks.filter(c => c.status === 'FAIL').map(c => ({ scope: c.scope, id: c.id })) }, null, 2))
  process.exitCode = report.summary.failed ? 1 : report.summary.unverified ? 2 : 0
}

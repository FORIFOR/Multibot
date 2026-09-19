// Captures the screens a reviewer needs, from the bundled UI served by the scripted TEST server
// (backend/scripts/demo_fake_server.py). These are layout/interaction evidence, not proof of real model behaviour.
//   UI_BASE_URL=http://127.0.0.1:8791 node frontend/scripts/ui-capture.mjs
import { chromium } from 'playwright-core'
import { mkdirSync, writeFileSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const base = process.env.UI_BASE_URL || 'http://127.0.0.1:8791'
const out = resolve(dirname(fileURLToPath(import.meta.url)), '../../artifacts/ui')
mkdirSync(out, { recursive: true })
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const record = []
try {
  const sizes = [['desktop', 1440, 900], ['mobile', 390, 844]]
  const open = async (width, height) => {
    const context = await browser.newContext({ viewport: { width, height }, locale: 'ja-JP', deviceScaleFactor: 1, reducedMotion: 'reduce' })
    const page = await context.newPage(); const errors = []
    page.on('pageerror', e => errors.push(e.message))
    return { context, page, errors }
  }
  const note = async (file, page, errors, width, height, state) => record.push({ file, url: page.url(), viewport: `${width}x${height}`, dpr: 1, state,
    data: 'scripted test server (not a real model)', overflow: await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), pageErrors: errors })
  // 1. The request screen at both sizes, in the same state: before this capture's request exists.
  for (const [name, width, height] of sizes) {
    const { context, page, errors } = await open(width, height)
    await page.goto(base, { waitUntil: 'networkidle' })
    await page.screenshot({ path: `${out}/${name}-home.png`, fullPage: true })
    await note(`${name}-home.png`, page, errors, width, height, 'request screen, request box empty'); await context.close()
  }
  // 2. The main task once, then the work screen at both sizes.
  let runUrl = ''
  for (const [name, width, height] of sizes) {
    const { context, page, errors } = await open(width, height)
    if (!runUrl) {
      await page.goto(base, { waitUntil: 'networkidle' })
      await page.locator('#request-goal').fill('この製品の紹介文を、分かりやすく作って。')
      await page.screenshot({ path: `${out}/desktop-home-filled.png` })
      await note('desktop-home-filled.png', page, errors, width, height, 'request screen, request written, main button enabled')
      await page.getByRole('button', { name: 'チームにお願いする', exact: true }).click()
      await page.waitForURL(/\/runs\//); runUrl = page.url().split('?')[0]
      await page.locator('.result-reader').waitFor({ timeout: 60000 })
    } else await page.goto(runUrl, { waitUntil: 'networkidle' })
    await page.waitForTimeout(800)
    await page.screenshot({ path: `${out}/${name}.png`, fullPage: true })
    await note(`${name}.png`, page, errors, width, height, await page.locator('.work-status strong').first().innerText())
    if (name === 'desktop') {
      await page.screenshot({ path: `${out}/desktop-first-screen.png` })
      await note('desktop-first-screen.png', page, errors, width, height, 'work screen, first screen only (no scrolling)')
    }
    if (name === 'mobile') {
      // Full-page captures do not paint an off-screen iframe, so a page deliverable is also captured inside the viewport.
      const reader = page.locator('.result-reader'); await reader.scrollIntoViewIfNeeded(); await page.waitForTimeout(900)
      await page.screenshot({ path: `${out}/mobile-results-viewport.png` })
      await note('mobile-results-viewport.png', page, errors, width, height, 'work screen scrolled to the results reader, viewport only')
    }
    // Panel-only shots: the sticky top bar would otherwise be painted over the panel. It stays visible in the page shots above.
    await page.addStyleTag({ content: '.top{visibility:hidden!important}' })
    // The same screen with a file that has no check record selected: the state a reviewer must be able to tell apart.
    const unchecked = page.locator('.result-file-list button').filter({ has: page.locator('.tab-mark') }).first()
    await unchecked.click(); await page.waitForTimeout(500)
    await page.locator('.simple-deliverables').screenshot({ path: `${out}/${name}-unchecked-file.png` })
    await note(`${name}-unchecked-file.png`, page, errors, width, height, `results panel only, file selected: ${(await unchecked.innerText()).trim()}`)
    if (name === 'desktop') {
      // What the panel looks like right after adopting: once for the unverified file, once for a passed one, with the record open.
      await page.locator('[data-adopt]').click(); await page.waitForTimeout(800)
      await page.locator('.simple-deliverables').screenshot({ path: `${out}/desktop-after-adopt-unverified.png` })
      await note('desktop-after-adopt-unverified.png', page, errors, width, height, 'results panel right after adopting the file that has no check record')
      await page.locator('.result-file-list button').filter({ hasNot: page.locator('.tab-mark') }).first().click(); await page.waitForTimeout(500)
      await page.locator('[data-adopt]').click(); await page.waitForTimeout(800)
      await page.locator('.result-record summary').click(); await page.waitForTimeout(400)
      await page.locator('.simple-deliverables').screenshot({ path: `${out}/desktop-after-adopt-passed-record-open.png` })
      await note('desktop-after-adopt-passed-record-open.png', page, errors, width, height, 'results panel after adopting a passed file, check record opened')
    }
    await context.close()
  }
} finally { await browser.close() }
writeFileSync(`${out}/capture.json`, JSON.stringify({ capturedAt: new Date().toISOString(), base, browser: 'Chrome (headless, channel=chrome)', locale: 'ja-JP', reducedMotion: true,
  note: 'Full-page captures in headless Chrome do not paint an off-screen iframe: judge a page (HTML) deliverable from the *-viewport images, never from the full-page ones.',
  images: record }, null, 2) + '\n')
console.log(JSON.stringify(record))
if (record.some(r => r.overflow || r.pageErrors.length)) process.exit(1)

// Captures the work screen with a file whose checks passed, BEFORE it is adopted, plus the other app screens, from the
// bundled UI on the scripted TEST server. Layout evidence only; not proof of real model behaviour.
//   UI_BASE_URL=http://127.0.0.1:8791 node frontend/scripts/work-capture.mjs
import { chromium } from 'playwright-core'
import { mkdirSync, writeFileSync } from 'node:fs'
const base = process.env.UI_BASE_URL || 'http://127.0.0.1:8791'
const out = new URL('../../artifacts/ui/obsidian-app', import.meta.url).pathname; mkdirSync(out, { recursive: true })
const browser = await chromium.launch({ channel: 'chrome', headless: true }); const shots = []
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: 'ja-JP' }); const page = await context.newPage()
const note = async (file, state) => shots.push({ file, viewport: page.viewportSize(), url: page.url(), state, horizontalOverflowPx: await page.evaluate(() => document.documentElement.scrollWidth - innerWidth) })
await page.goto(base + '/', { waitUntil: 'networkidle' }); await page.locator('#request-goal').fill('この製品の紹介文を、分かりやすく作って。')
await page.getByRole('button', { name: 'チームにお願いする', exact: true }).click(); await page.waitForURL(/\/runs\//)
const id = page.url().split('/runs/')[1].split('?')[0]
for (let i = 0; i < 120; i++) { if ((await (await fetch(`${base}/api/runs/${id}`)).json()).status === 'completed') break; await page.waitForTimeout(500) }
await page.reload({ waitUntil: 'networkidle' }); await page.locator('.result-file-list button', { hasText: 'index.html' }).click(); await page.waitForTimeout(800)
for (const [w, h] of [[1440, 900], [1100, 800], [768, 1024], [390, 844]]) {
  await page.setViewportSize({ width: w, height: h }); await page.waitForTimeout(500)
  if (w < 1001) await page.locator('.room-view-nav button').nth(1).click()
  await page.evaluate(() => scrollTo(0, 0)); await page.waitForTimeout(300)
  const top = await page.locator('.result-reader').evaluate(e => Math.round(e.getBoundingClientRect().top))
  await page.screenshot({ path: `${out}/work-${w}-passed-before-adopt.png` }); await note(`work-${w}-passed-before-adopt.png`, `checked file selected, not adopted; first screen only; document starts at y=${top} of ${h}`)
}
// keyboard only: reach the main action and show where focus is
await page.setViewportSize({ width: 1440, height: 900 }); await page.evaluate(() => scrollTo(0, 0)); await page.locator('.result-file-list button', { hasText: 'index.html' }).focus()
const order = []
for (let i = 0; i < 12; i++) { await page.keyboard.press('Tab'); const t = await page.evaluate(() => (document.activeElement?.innerText || document.activeElement?.tagName || '').trim().slice(0, 24)); order.push(t); if (await page.evaluate(() => document.activeElement?.hasAttribute('data-adopt'))) break }
await page.screenshot({ path: `${out}/work-1440-focus-adopt.png` }); await note('work-1440-focus-adopt.png', 'keyboard only from the file tab. Focus order: ' + order.join(' → '))
await page.keyboard.press('Enter'); await page.locator('.chosen-pill').waitFor(); await page.waitForTimeout(400)
const focused = await page.evaluate(() => document.activeElement?.className || document.activeElement?.tagName)
await page.screenshot({ path: `${out}/work-1440-after-keyboard-adopt.png` }); await note('work-1440-after-keyboard-adopt.png', `adopted with Enter; focus is now on: ${focused}`)
for (const [w, h] of [[1440, 900], [390, 844]]) { await page.setViewportSize({ width: w, height: h })
  for (const [n, u] of [['my-team', '/settings'], ['work-list', '/runs'], ['welcome', '/welcome']]) { await page.goto(base + u, { waitUntil: 'networkidle' }); await page.waitForTimeout(600); await page.screenshot({ path: `${out}/${n}-${w}.png` }); await note(`${n}-${w}.png`, 'first screen') } }
await browser.close()
writeFileSync(`${out}/capture.json`, JSON.stringify({ capturedAt: new Date().toISOString(), base, browser: 'Chrome (headless, channel=chrome)', motion: 'normal', data: 'scripted TEST server; not real model output', shots }, null, 1))
for (const s of shots) console.log(s.file, s.horizontalOverflowPx > 1 ? 'OVERFLOW' : 'ok', '|', s.state.slice(0, 150))

// Captures the Ask screen (/) states a reviewer needs, from the bundled UI served by the scripted TEST server
// (backend/scripts/demo_fake_server.py). Layout/interaction evidence only; not proof of real model behaviour.
//   UI_BASE_URL=http://127.0.0.1:8791 node frontend/scripts/ask-capture.mjs
import { chromium } from 'playwright-core'
import { mkdirSync, writeFileSync } from 'node:fs'
const base = process.env.UI_BASE_URL || 'http://127.0.0.1:8791'
const out = new URL('../../artifacts/ui/obsidian-home', import.meta.url).pathname
mkdirSync(out, { recursive: true })
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const shots = []
const long = '添付した3つの資料（製品説明、価格表、問い合わせの記録）だけを使い、初めての人が10分で読める導入ガイド guide.md を作ってください。前提条件、最初の手順、よくあるつまずき、制約の順にまとめ、根拠の節を示し、確かめられない点は未確認と明記してください。'
async function open(width, height, lang = 'ja') {
  const context = await browser.newContext({ viewport: { width, height }, locale: lang === 'ja' ? 'ja-JP' : 'en-US' })
  if (lang === 'en') await context.addInitScript(() => { try { localStorage.setItem('agentteam.lang', 'en') } catch { /* private mode */ } })
  const page = await context.newPage()
  await page.goto(base + '/', { waitUntil: 'networkidle' }); await page.locator('#request-goal').waitFor()
  return { context, page }
}
async function shot(page, name, state, fullPage = false) {
  const view = page.viewportSize()
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)
  await page.screenshot({ path: `${out}/${name}.png`, fullPage })
  shots.push({ file: `${name}.png`, viewport: view, url: page.url(), state, fullPage, horizontalOverflowPx: overflow })
}
for (const [w, h] of [[1440, 900], [1100, 900], [768, 1000], [390, 844]]) {
  const { context, page } = await open(w, h)
  await shot(page, `ask-${w}-first-screen`, 'empty request; past requests as on the test server')
  await shot(page, `ask-${w}-full`, 'empty request', true)
  if (w === 1440 || w === 390) {
    await page.locator('#request-goal').fill(long)
    await shot(page, `ask-${w}-long-input`, `${long.length} characters of Japanese typed; main button enabled`)
    await page.locator('details.more > summary').first().click()
    await shot(page, `ask-${w}-open-materials`, 'materials and budget opened', true)
    await page.locator('details.more > summary').first().click()
    await page.locator('details.more > summary').nth(1).click()
    await shot(page, `ask-${w}-open-conditions`, 'output conditions opened', true)
    await page.locator('details.more > summary').nth(1).click()
    await page.locator('.team-selection-mode label').nth(1).click()
    await shot(page, `ask-${w}-choose-team`, 'choose teammates myself', true)
    await page.locator('.team-selection-mode label').first().click()
    await page.locator('.request-disclosure summary').click()
    await shot(page, `ask-${w}-open-tools`, 'tool permissions opened', true)
  }
  if (w === 1440) {
    await page.locator('.request-disclosure summary').click(); await page.evaluate(() => scrollTo(0, 0))
    await page.locator('#request-goal').focus()
    const order = []
    for (let i = 0; i < 4; i++) { await page.keyboard.press('Tab'); order.push(await page.evaluate(() => (document.activeElement?.innerText || document.activeElement?.closest('label')?.innerText || document.activeElement?.tagName || '').trim().slice(0, 30))) }
    await shot(page, 'ask-1440-focus-main-button', 'keyboard only: Tab x4 from the request field. Focus order: ' + order.join(' → '))
    await page.evaluate(() => document.activeElement?.blur())
    const tile = await page.locator('.home-companion .bot-custom-emoji').first().boundingBox()
    await page.screenshot({ path: `${out}/ask-1440-bot-rest-zoom.png`, clip: { x: tile.x - 20, y: tile.y - 20, width: 420, height: tile.height + 40 } })
    await page.mouse.move(tile.x + tile.width / 2, tile.y + tile.height / 2); await page.waitForTimeout(400)
    await page.screenshot({ path: `${out}/ask-1440-bot-hover-zoom.png`, clip: { x: tile.x - 20, y: tile.y - 20, width: 420, height: tile.height + 40 } })
    shots.push({ file: 'ask-1440-bot-hover-zoom.png', viewport: page.viewportSize(), url: page.url(), state: 'pointer resting on the coordinator tile; ask-1440-bot-rest-zoom.png is the same clip without the pointer. transform=' + await page.locator('.home-companion .bot-custom-emoji').first().evaluate(e => getComputedStyle(e).transform), fullPage: false, horizontalOverflowPx: 0 })
    await page.mouse.move(5, 5)
  }
  await context.close()
}
{ const { context, page } = await open(390, 844, 'en'); await shot(page, 'ask-390-en-first-screen', 'English, empty'); await context.close() }
await browser.close()
writeFileSync(`${out}/capture.json`, JSON.stringify({ capturedAt: new Date().toISOString(), base, browser: 'Chrome (headless, channel=chrome)', motion: 'normal', data: 'scripted TEST server; not real model output', shots }, null, 1))
for (const s of shots) console.log(s.file, s.horizontalOverflowPx > 1 ? `OVERFLOW ${s.horizontalOverflowPx}px` : 'ok', '|', s.state.slice(0, 110))

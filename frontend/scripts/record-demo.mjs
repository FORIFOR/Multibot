// Records a paced walkthrough of the UI as video (webm) using the locally installed Chrome.
// BASE=http://127.0.0.1:8791 OUT=/tmp/agentteam-demo node scripts/record-demo.mjs
// The demo server uses the scripted FAKE provider; the recording must be labelled as such wherever it is shown.
import { chromium } from 'playwright-core'
import fs from 'node:fs'
const base = process.env.BASE || 'http://127.0.0.1:8791'
const out = process.env.OUT || '/tmp/agentteam-demo'
fs.mkdirSync(out, { recursive: true })
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, recordVideo: { dir: out, size: { width: 1440, height: 900 } }, deviceScaleFactor: 1 })
const page = await ctx.newPage()
const sleep = (ms) => page.waitForTimeout(ms)
await page.goto(base + '/', { waitUntil: 'networkidle' })
await sleep(1500)
const goal = 'この製品説明をもとに、紹介LPとSNS投稿案を作って。足りない情報は調べて、公開前の状態まで仕上げて。'
await page.click('textarea')
for (const ch of goal) { await page.keyboard.type(ch); await sleep(28) }
await sleep(900)
await page.click('button:has-text("開始")')
await page.waitForURL(/\/runs\//, { timeout: 15000 })
// watch the team work: chat tab is default; keep it until the review finding arrives
for (let i = 0; i < 40; i++) {
  await sleep(1000)
  const n = await page.locator('.msg').count()
  if (n >= 4) break
}
await sleep(1500)
await page.click('button:has-text("時系列")')
await sleep(2200)
await page.click('button:has-text("チームチャット")')
await sleep(1200)
// wait for completion
for (let i = 0; i < 40; i++) { await sleep(1000); if (await page.locator('.tag.status-completed').count()) break }
await sleep(800)
// artifact revision trace: click r1 then r2
const r1 = page.locator('.revs button', { hasText: 'r1' })
if (await r1.count()) { await r1.first().click(); await sleep(1500) }
const r2 = page.locator('.revs button', { hasText: 'r2' })
if (await r2.count()) { await r2.first().click(); await sleep(1500) }
await page.click('button:has-text("最終報告")')
await sleep(2500)
await page.click('button:has-text("承認")')
await sleep(1200)
await page.click('button:has-text("最終報告")')
await sleep(1500)
await ctx.close()
await browser.close()
const files = fs.readdirSync(out).filter((f) => f.endsWith('.webm'))
console.log(JSON.stringify({ out, files }))

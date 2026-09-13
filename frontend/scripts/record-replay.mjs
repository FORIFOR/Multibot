// Records a REPLAY of a real, already-finished run in the UI (no LLM calls). BASE and RUN via env.
import { chromium } from 'playwright-core'
import fs from 'node:fs'
const base = process.env.BASE || 'http://127.0.0.1:8793', run = process.env.RUN, out = process.env.OUT || '/tmp/agentteam-replay'
fs.mkdirSync(out, { recursive: true })
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, recordVideo: { dir: out, size: { width: 1440, height: 900 } } })
const page = await ctx.newPage(); const sleep = (ms) => page.waitForTimeout(ms)
await page.goto(`${base}/`, { waitUntil: 'networkidle' }); await page.evaluate(() => localStorage.setItem('agentteam.lang', 'ja')); await page.reload({ waitUntil: 'networkidle' }); await sleep(1500)
await page.goto(`${base}/runs/${run}`, { waitUntil: 'networkidle' }); await sleep(2500)
// team → open the researcher task detail
const t1 = page.locator('.task', { hasText: 't1' }).first(); if (await t1.count()) { await t1.click(); await sleep(2200) }
// chat (delivered messages)
await page.click('button:has-text("チームチャット")'); await sleep(2500)
// artifacts: review.md then research-final-r2.md
for (const name of ['review.md', 'research.md', 'research-final-r2.md']) { const a = page.locator('.art', { hasText: name }).first(); if (await a.count()) { await a.click(); await sleep(2600) } }
// timeline
await page.click('button:has-text("時系列")'); await sleep(2500)
await page.locator('.pane .body').nth(2).evaluate((el) => el.scrollBy({ top: 600, behavior: 'smooth' })); await sleep(1800)
// report
await page.click('button:has-text("最終報告")'); await sleep(3000)
await ctx.close(); await browser.close()
console.log(JSON.stringify({ out, files: fs.readdirSync(out) }))

// Headless UI smoke against a running server (uses the locally installed Chrome; no browser download).
// BASE=http://127.0.0.1:8791 node scripts/ui-smoke.mjs  -> screenshots in /tmp/agentteam-shots, prints console/page errors.
import { chromium } from 'playwright-core'
const base = process.env.BASE || 'http://127.0.0.1:8791'
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
const errors = []
page.on('pageerror', (e) => errors.push('pageerror: ' + e.message))
page.on('console', (m) => { if (m.type() === 'error') errors.push('console: ' + m.text()) })
await page.goto(base + '/', { waitUntil: 'networkidle' })
await page.screenshot({ path: '/tmp/agentteam-shots/home.png' })
await page.fill('textarea', 'この製品説明から紹介LPとSNS投稿案を作って')
await page.click('button:has-text("開始")')
await page.waitForURL(/\/runs\//, { timeout: 10000 })
await page.waitForTimeout(2500)
await page.screenshot({ path: '/tmp/agentteam-shots/run.png', fullPage: true })
await page.click('button:has-text("時系列")')
await page.waitForTimeout(500)
await page.screenshot({ path: '/tmp/agentteam-shots/run-timeline.png' })
await page.click('button:has-text("最終報告")')
await page.waitForTimeout(500)
await page.screenshot({ path: '/tmp/agentteam-shots/run-report.png' })
await page.goto(base + '/settings', { waitUntil: 'networkidle' })
await page.click('button:has-text("システムプロンプト")')
await page.waitForTimeout(300)
await page.screenshot({ path: '/tmp/agentteam-shots/settings.png', fullPage: true })
console.log(JSON.stringify({ url: page.url(), errors }))
await browser.close()

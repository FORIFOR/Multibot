// Headless UI smoke against a running server (uses the locally installed Chrome; no browser download).
//   BASE=http://127.0.0.1:8791 LANG_UI=ja node scripts/ui-smoke.mjs   (LANG_UI=ja|en; default ja)
// Drives Home → start a request → Run view (chat / timeline / final report) → Settings, then waits for the run to
// reach a terminal status through the API. Screenshots go to $SHOTS (default /tmp/agentteam-shots).
// Exits 1 on any console/page error, a missing label, or a run that does not finish — so CI can gate on it.
import { chromium } from 'playwright-core'
import { mkdirSync, cpSync, rmSync, readFileSync } from 'node:fs'
import { execFileSync } from 'node:child_process'
import { resolve } from 'node:path'

// Always test current source, including when invoked by the original CI job.
// The fake server serves this path dynamically; no checked-in bundle is accepted.
execFileSync('npm', ['run', 'build'], { stdio: 'inherit' })
const packagedUI = resolve('../backend/agentteam/ui')
rmSync(packagedUI, { recursive: true, force: true })
cpSync(resolve('dist'), packagedUI, { recursive: true })
if (readFileSync(resolve('dist/index.html'), 'utf8') !== readFileSync(resolve(packagedUI, 'index.html'), 'utf8')) throw new Error('Current UI was not copied')

const base = process.env.BASE || 'http://127.0.0.1:8791'
const lang = process.env.LANG_UI === 'en' ? 'en' : 'ja'
const shots = process.env.SHOTS || '/tmp/agentteam-shots'
mkdirSync(shots, { recursive: true })
const L = lang === 'en'
  ? { start: 'Start', timeline: 'Timeline', report: 'Final report', prompt: 'Instructions, model & advanced settings', brand: 'Agent Team', settingsNav: 'Settings' }
  : { start: '開始', timeline: '時系列', report: '最終報告', prompt: '任せる仕事・モデル・詳細設定', brand: 'Agent Team', settingsNav: '設定' }

const browser = await chromium.launch({ channel: 'chrome', headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: lang === 'en' ? 'en-US' : 'ja-JP' })
const page = await context.newPage()
const errors = []
page.on('pageerror', (e) => errors.push('pageerror: ' + e.message))
page.on('console', (m) => { if (m.type() === 'error') errors.push('console: ' + m.text()) })

let runStatus = null
try {
  await page.goto(base + '/', { waitUntil: 'networkidle' })
  await page.waitForSelector(`text=${L.settingsNav}`, { timeout: 10000 })
  await page.screenshot({ path: `${shots}/home-${lang}.png` })
  await page.fill('textarea', lang === 'en' ? 'Make a launch page and three post drafts from this product description' : 'この製品説明から紹介LPとSNS投稿案を作って')
  await page.click(`button:has-text("${L.start}")`, { timeout: 10000 })
  await page.waitForURL(/\/runs\//, { timeout: 10000 })
  const runId = page.url().match(/\/runs\/([^/?#]+)/)[1]
  await page.waitForTimeout(2500)
  await page.screenshot({ path: `${shots}/run-${lang}.png`, fullPage: true })
  await page.click(`button:has-text("${L.timeline}")`)
  await page.waitForTimeout(500)
  await page.screenshot({ path: `${shots}/run-timeline-${lang}.png` })
  await page.click(`button:has-text("${L.report}")`)
  await page.waitForTimeout(500)
  await page.screenshot({ path: `${shots}/run-report-${lang}.png` })
  // the scripted provider finishes within seconds; wait for a terminal status via the API
  for (let i = 0; i < 60; i++) {
    const r = await (await fetch(`${base}/api/runs/${runId}`)).json()
    runStatus = r.status
    if (['completed', 'partial', 'failed', 'cancelled', 'interrupted', 'blocked'].includes(runStatus)) break
    await new Promise((res) => setTimeout(res, 500))
  }
  await page.goto(base + '/settings', { waitUntil: 'networkidle' })
  await page.locator('.bot-settings-card summary').first().click()
  await page.locator('.custom-bot-add').click()
  const form = page.locator('#custom-bot-form')
  await form.getByLabel(lang === 'en' ? 'Name' : '名前', { exact: true }).fill(lang === 'en' ? 'QA Panda' : '確認パンダ')
  await form.getByLabel(lang === 'en' ? 'What should this bot do?' : '任せたいこと', { exact: true }).fill('Read supplied sources and summarize without inventing facts.')
  await form.getByRole('button', { name: lang === 'en' ? 'Panda' : 'パンダ', exact: true }).click()
  await form.locator('button[type="submit"]').click()
  await page.locator('#custom-bot-created').waitFor()
  const custom = (await (await fetch(`${base}/api/agents`)).json()).find(a => a.display_name === (lang === 'en' ? 'QA Panda' : '確認パンダ'))
  if (!custom || custom.emoji !== '🐼') throw new Error('Custom bot was not persisted by the real API')
  await page.reload({ waitUntil: 'networkidle' })
  await page.locator(`#agent-card-${custom.id}`).waitFor()
  await page.locator(`#agent-card-${custom.id} summary`).click()
  await page.waitForTimeout(300)
  await page.screenshot({ path: `${shots}/settings-${lang}.png`, fullPage: true })
} catch (e) {
  errors.push('step: ' + (e.message || String(e)).split('\n')[0])
}
await browser.close()
const ok = errors.length === 0 && runStatus === 'completed'
console.log(JSON.stringify({ lang, url: page.url(), run_status: runStatus, errors, ok }))
process.exit(ok ? 0 : 1)

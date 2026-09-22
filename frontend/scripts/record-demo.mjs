// Records the real app doing the real task against the configured model. No fixtures: this drives the same server a
// user would run. Output: a raw webm plus a timeline of what happened when, for the edit.
//   DEMO_BASE=http://127.0.0.1:8799 node frontend/scripts/record-demo.mjs <outDir>
import { chromium } from 'playwright-core'
import { writeFileSync, readFileSync } from 'node:fs'
const base = process.env.DEMO_BASE || 'http://127.0.0.1:8799'
const lang = process.env.DEMO_LANG === 'en' ? 'en' : 'ja'
const L = lang === 'en'
  ? { request: 'Using only the attached product.md, write guide.md: a short onboarding guide with prerequisites, first steps and limits. Mark anything the source does not say as unverified.',
      filename: 'Output filename', route: 'Create one document from supplied material', send: 'Ask the team', record: 'See the check record' }
  : { request: '添付した product.md だけを使い、初めての人向けの導入ガイド guide.md を作ってください。前提条件・最初の手順・制約の順にまとめ、資料にない内容は未確認と明記してください。',
      filename: '成果物のファイル名', route: '添えた資料から1つの文書を作る', send: 'チームにお願いする', record: '確認の記録を見る' }
const out = process.argv[2]
const source = readFileSync(new URL('./demo-source.md', import.meta.url).pathname, 'utf8')
const marks = []
const t0 = Date.now()
const mark = (what) => { const at = (Date.now() - t0) / 1000; marks.push({ at: Number(at.toFixed(2)), what }); console.log(at.toFixed(1).padStart(7), what) }

const browser = await chromium.launch({ channel: 'chrome', headless: true })
const context = await browser.newContext({ viewport: { width: 1280, height: 800 }, locale: lang === 'en' ? 'en-US' : 'ja-JP',
  recordVideo: { dir: out, size: { width: 1280, height: 800 } } })
await context.addInitScript((l) => { try { localStorage.setItem('agentteam.lang', l) } catch {} }, lang)
const page = await context.newPage()
await page.goto(base + '/', { waitUntil: 'networkidle' })
await page.locator('#request-goal').waitFor()
mark('ask screen open')
await page.waitForTimeout(1200)

// type the request the way a person would
await page.locator('#request-goal').click()
for (const ch of L.request) {
  await page.keyboard.type(ch, { delay: 18 })
}
mark('request typed')
await page.waitForTimeout(800)

// attach the source file through the real picker
await page.locator('details.more > summary').first().click()
await page.waitForTimeout(600)
await page.locator('#run-attachments').setInputFiles({ name: 'product.md', mimeType: 'text/markdown', buffer: Buffer.from(source) })
mark('product.md attached')
await page.waitForTimeout(1200)
await page.locator('details.more > summary').first().click()
await page.waitForTimeout(500)

// name the file the team must deliver, and ask for the two-step route: one writes it, another checks it
await page.locator('details.more > summary').nth(1).click()
await page.waitForTimeout(700)
await page.getByLabel(L.filename, { exact: true }).fill('guide.md')
await page.waitForTimeout(500)
await page.getByLabel(L.route, { exact: true }).check()
mark('output file + two-step route chosen')
await page.waitForTimeout(1500)
await page.locator('details.more > summary').nth(1).click()
await page.waitForTimeout(500)

await page.getByRole('button', { name: L.send, exact: true }).click()
await page.waitForURL(/\/runs\//)
const runId = page.url().split('/runs/')[1].split('?')[0]
mark('sent -> work screen ' + runId)
await page.locator('.room-goal h1').waitFor()
await page.waitForTimeout(2500)

// let the team work; keep the conversation in view and note each milestone
let lastStatus = '', lastFiles = -1
for (let i = 0; i < 300; i++) {
  const run = await (await fetch(`${base}/api/runs/${runId}`)).json()
  const files = run.artifacts.filter((a) => a.logical_path !== 'final-report.md').length
  if (run.status !== lastStatus) { mark('status: ' + run.status); lastStatus = run.status }
  if (files !== lastFiles) { mark(`files published: ${files}`); lastFiles = files }
  if (['completed', 'partial', 'failed', 'cancelled', 'interrupted', 'blocked'].includes(run.status)) break
  await page.waitForTimeout(5000)
}
mark('run finished: ' + lastStatus)
await page.reload({ waitUntil: 'networkidle' })
await page.waitForTimeout(2000)

// show the result and the check record, then choose the version
const tab = page.locator('.result-file-list button', { hasText: 'guide.md' })
if (await tab.count()) { await tab.first().click(); mark('opened guide.md'); await page.waitForTimeout(2500) }
const record = page.getByRole('button', { name: L.record, exact: true })
if (await record.count()) { await record.first().click(); mark('opened the check record'); await page.waitForTimeout(3500) }
const adopt = page.locator('[data-adopt]')
if (await adopt.count()) { await adopt.first().click(); mark('adopted a version'); await page.waitForTimeout(2500) }
await page.waitForTimeout(1500)
mark('end')

const runFinal = await (await fetch(`${base}/api/runs/${runId}`)).json()
await context.close()
await browser.close()
writeFileSync(`${out}/timeline.json`, JSON.stringify({ recordedAt: new Date().toISOString(), base, runId,
  status: runFinal.status, language: lang, model: 'local Ollama agentteam-qwen35-9b-16k', usage: runFinal.usage,
  artifacts: runFinal.artifacts.map((a) => ({ path: a.logical_path, revision: a.revision })),
  team: (runFinal.config_snapshot?.team_recommendation?.members || []).map((m) => ({ name: m.name, specialty: m.specialty })),
  marks }, null, 1))
console.log('done:', runFinal.status, runFinal.usage.model_calls, 'calls')

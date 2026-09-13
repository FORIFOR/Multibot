// Exercises the live secured queue UI with the original workplace request and a
// real local provider. The server must have one execution slot and a probed model.
import { chromium } from 'playwright-core'
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs'
import { randomUUID } from 'node:crypto'
import assert from 'node:assert/strict'

const root = process.env.DURABLE_ROOT
const recordFile = process.env.REAL_REQUEST_FILE
if (!root || !recordFile) throw new Error('DURABLE_ROOT and REAL_REQUEST_FILE are required')
const base = 'http://127.0.0.1:8810'
const key = readFileSync(`${root}/forifor.key`, 'utf8').trim()
const record = JSON.parse(readFileSync(recordFile, 'utf8'))
const shots = `${root}/screenshots`; mkdirSync(shots, { recursive: true })
const headers = { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' }
let first, queued
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const errors = [], checks = []
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 960 }, locale: 'ja-JP' })
  const page = await context.newPage()
  page.on('pageerror', error => errors.push(error.message))
  let keyedSubmission = false
  page.on('request', request => { if (request.method() === 'POST' && request.url() === base + '/api/runs') keyedSubmission ||= !!request.headers()['idempotency-key'] })
  await page.goto(base)
  await page.getByLabel(/アクセスキー|Access key/).fill(key)
  await page.getByRole('button', { name: /^(ログイン|Sign in)$/ }).click()
  await page.getByRole('button', { name: /^(開始|Start)$/ }).waitFor()
  const started = await fetch(base + '/api/runs', { method: 'POST', headers: { ...headers, 'Idempotency-Key': randomUUID() },
    body: JSON.stringify({ goal: record.goal, inputs: record.inputs, start: true }) })
  assert.equal(started.status, 202); first = (await started.json()).run_id
  await page.locator('textarea').first().fill(record.goal)
  await page.getByText(/添付・URL・予算|Attachments/).click()
  await page.locator('textarea').nth(1).fill([record.inputs.text || '', ...record.inputs.files.map(file => file.content || '')].join('\n'))
  await page.getByRole('button', { name: /^(開始|Start)$/ }).click()
  await page.waitForURL(/\/runs\//)
  queued = page.url().split('/').pop()
  await page.getByText(/実行枠が空き次第、開始します。|Starts when an execution slot/).waitFor()
  assert.equal(keyedSubmission, true)
  await page.waitForFunction(() => [...document.querySelectorAll('.reveal')].every(el => getComputedStyle(el).opacity === '1'))
  await page.screenshot({ path: `${shots}/actual-queued-request.png` })
  checks.push('Real browser submission sends an idempotency key and displays the durable waiting state')
  await page.getByRole('button', { name: /^(停止|Stop)$/ }).click()
  await page.locator('.runhead .status-cancelled').waitFor()
  const result = await (await fetch(base + '/api/runs/' + queued, { headers })).json()
  assert.equal(result.status, 'cancelled'); assert.equal(result.usage.model_calls, 0)
  await page.screenshot({ path: `${shots}/cancelled-before-model.png` })
  checks.push('Browser cancellation updates through real API/SSE and makes zero model calls for the queued request')
  assert.equal(errors.length, 0)
  writeFileSync(`${root}/durable-browser.json`, JSON.stringify({ recorded_at: new Date().toISOString(), checks, page_errors: errors,
    actual_background_run: first, actual_queued_run: queued, business_success_claimed: false }, null, 2) + '\n')
  console.log(JSON.stringify({ passed: checks.length, page_errors: errors }))
} finally {
  for (const id of [queued, first].filter(Boolean)) await fetch(base + '/api/runs/' + id + '/cancel', { method: 'POST', headers })
  await browser.close()
}

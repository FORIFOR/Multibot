// Real browser + authenticated HTTP service. Supply keys issued by `agentteam access`.
import { chromium } from 'playwright-core'
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs'

const base = process.env.BASE
const adminKey = process.env.ADMIN_KEY_FILE
const operatorKey = process.env.OPERATOR_KEY_FILE
const auditorKey = process.env.AUDITOR_KEY_FILE
const shots = process.env.SHOTS
if (!base || !adminKey || !operatorKey || !shots) throw new Error('BASE, ADMIN_KEY_FILE, OPERATOR_KEY_FILE and SHOTS are required')
mkdirSync(shots, { recursive: true })
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const errors = []
const checks = []
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 960 }, locale: 'ja-JP' })
  const page = await context.newPage()
  page.on('pageerror', e => errors.push(e.message))
  page.on('console', message => {
    // A signed-out visit deliberately checks /api/auth/me and receives 401.
    if (message.type() === 'error' && !message.text().includes('the server responded with a status of 401') &&
        !message.text().includes('the server responded with a status of 503')) errors.push(message.text())
  })
  await page.goto(base)
  await page.getByLabel(/アクセスキー|Access key/).waitFor()
  await page.screenshot({ path: `${shots}/login.png` })
  await page.getByLabel(/アクセスキー|Access key/).fill(readFileSync(adminKey, 'utf8').trim())
  await page.getByRole('button', { name: /^(ログイン|Sign in)$/ }).click()
  await page.getByRole('link', { name: /^(設定|Settings)$/ }).waitFor()
  checks.push('admin login and settings navigation')
  if (process.env.RUN_ID) {
    await page.goto(`${base}/runs/${process.env.RUN_ID}`)
    await page.getByRole('heading', { level: 1 }).waitFor()
    await page.screenshot({ path: `${shots}/authenticated-run.png` })
    checks.push('authenticated replay of an actual saved run')
  }
  await page.getByRole('button', { name: /^(ログアウト|Sign out)$/ }).click()
  await page.getByLabel(/アクセスキー|Access key/).waitFor()
  checks.push('logout returns to login')
  await page.getByLabel(/アクセスキー|Access key/).fill(readFileSync(operatorKey, 'utf8').trim())
  await page.getByRole('button', { name: /^(ログイン|Sign in)$/ }).click()
  await page.getByRole('button', { name: /^(ログアウト|Sign out)$/ }).waitFor()
  if (await page.getByRole('link', { name: /^(設定|Settings)$/ }).count()) throw new Error('operator can see administrator settings navigation')
  await page.getByRole('heading', { level: 1 }).waitFor()
  await page.waitForFunction(() => [...document.querySelectorAll('.reveal')].every(el => getComputedStyle(el).opacity === '1'))
  await page.screenshot({ path: `${shots}/operator-home.png` })
  checks.push('operator view excludes administrator configuration')
  if (auditorKey) {
    await page.getByRole('button', { name: /^(ログアウト|Sign out)$/ }).click()
    await page.getByLabel(/アクセスキー|Access key/).fill(readFileSync(auditorKey, 'utf8').trim())
    await page.getByRole('button', { name: /^(ログイン|Sign in)$/ }).click()
    await page.getByRole('heading', { name: /^(運用状況|Operations)$/ }).waitFor()
    // This actual staging configuration has never passed a capability probe.
    await page.getByText(/^(実行条件の確認が必要|Execution prerequisites need attention)$/).waitFor()
    await page.getByRole('heading', { name: /^(直近の監査記録|Recent audit records)$/ }).waitFor()
    if (await page.getByRole('link', { name: /^(設定|Settings|依頼|Requests)$/ }).count()) throw new Error('auditor received workspace navigation')
    await page.screenshot({ path: `${shots}/auditor-operations.png` })
    await page.setViewportSize({ width: 390, height: 844 })
    if (await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)) throw new Error('mobile operations page overflows the viewport')
    await page.screenshot({ path: `${shots}/auditor-operations-mobile.png` })
    checks.push('auditor sees actual degraded readiness and audit records without workspace controls')
  }
  if (errors.length) throw new Error(errors.join('\n'))
  writeFileSync(`${shots}/browser-result.json`, JSON.stringify({ checks, page_errors: errors }, null, 2) + '\n')
  console.log(JSON.stringify({ passed: checks.length, page_errors: errors }))
  await context.close()
} finally { await browser.close() }

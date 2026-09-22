// Drives the main task with the KEYBOARD ONLY, and captures what the screens show while the network is slow or
// failing, from the bundled UI on the scripted TEST server (backend/scripts/demo_fake_server.py).
// Interaction and state evidence; it is not a real device and not proof of real model behaviour.
//   UI_BASE_URL=http://127.0.0.1:8791 node frontend/scripts/journey-capture.mjs
import { chromium } from 'playwright-core'
import { mkdirSync, writeFileSync } from 'node:fs'

const base = process.env.UI_BASE_URL || 'http://127.0.0.1:8791'
const out = new URL('../../artifacts/ui/obsidian-journey', import.meta.url).pathname
mkdirSync(out, { recursive: true })
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const shots = []
const focused = (page) => page.evaluate(() => {
  const el = document.activeElement
  if (!el || el === document.body) return 'body (nothing focused)'
  const label = (el.innerText || el.getAttribute('aria-label') || el.getAttribute('placeholder') || el.id || el.tagName).trim().replace(/\s+/g, ' ')
  return `${el.tagName.toLowerCase()}${el.id ? '#' + el.id : ''}: ${label.slice(0, 40)}`
})
async function shot(page, name, state) {
  await page.screenshot({ path: `${out}/${name}.png` })
  shots.push({ file: `${name}.png`, viewport: page.viewportSize(), url: page.url(), state,
               horizontalOverflowPx: await page.evaluate(() => document.documentElement.scrollWidth - innerWidth) })
}

// 1. Keyboard only, all the way from the request to the chosen version.
{
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: 'ja-JP' })
  const page = await context.newPage()
  await page.goto(base + '/', { waitUntil: 'networkidle' })
  await page.locator('#request-goal').waitFor()
  const order = []
  const tabTo = async (predicate, limit = 25) => {
    for (let i = 0; i < limit; i++) {
      await page.keyboard.press('Tab')
      const where = await focused(page)
      order.push(where)
      if (await page.evaluate(predicate)) return where
    }
    throw new Error('never reached: ' + predicate.toString() + ' | ' + order.join(' → '))
  }
  await page.keyboard.press('Tab')  // from the address bar into the page
  order.push(await focused(page))
  await tabTo(() => document.activeElement?.id === 'request-goal')
  await shot(page, 'keyboard-1-request-field', 'Tab only: focus in the request field. Order so far: ' + order.join(' → '))
  await page.keyboard.type('この製品の紹介文を、分かりやすく作って。')
  const button = await tabTo(() => document.activeElement?.closest('.ask')?.matches('form') && document.activeElement?.type === 'submit')
  await shot(page, 'keyboard-2-main-button', 'Tab only: focus on the main action (' + button + '). Nothing has been sent yet')
  await page.keyboard.press('Enter')
  await page.waitForURL(/\/runs\//)
  const runId = page.url().split('/runs/')[1].split('?')[0]
  const firstFocus = await focused(page)
  await page.locator('.room-goal h1').waitFor()
  await page.waitForTimeout(300)
  await shot(page, 'keyboard-3-work-screen', `Enter sent the request; the work screen opened. Focus while it was still loading: ${firstFocus}. Focus once it had something to show: ${await focused(page)}`)
  for (let i = 0; i < 120; i++) { if ((await (await fetch(`${base}/api/runs/${runId}`)).json()).status === 'completed') break; await page.waitForTimeout(500) }
  await page.reload({ waitUntil: 'networkidle' })
  await page.locator('.result-file-list button').first().waitFor()
  await page.locator('.result-file-list button', { hasText: 'index.html' }).focus()
  const adoptOrder = []
  for (let i = 0; i < 20; i++) {
    await page.keyboard.press('Tab')
    adoptOrder.push(await focused(page))
    if (await page.evaluate(() => document.activeElement?.hasAttribute('data-adopt'))) break
  }
  await shot(page, 'keyboard-4-focus-adopt', 'Tab from the file tab to the main action. Order: ' + adoptOrder.join(' → '))
  await page.keyboard.press('Enter')
  await page.locator('.chosen-pill').waitFor()
  await page.waitForTimeout(400)
  await shot(page, 'keyboard-5-adopted', 'Enter adopted this version. Focus moved to: ' + await focused(page))
  await page.keyboard.press('Tab')
  await shot(page, 'keyboard-6-after-adopt-next', 'Next Tab after adopting lands on: ' + await focused(page))
  await context.close()
}

// 2. What the request screen shows while the network is slow, and when it fails.
{
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: 'ja-JP' })
  const page = await context.newPage()
  let release
  await page.route('**/api/runs', async (route) => {
    if (route.request().method() !== 'POST') return route.fallback()
    await new Promise((r) => { release = r })
    await route.fallback()
  })
  await page.goto(base + '/', { waitUntil: 'networkidle' })
  await page.locator('#request-goal').fill('この製品の紹介文を、分かりやすく作って。')
  await page.getByRole('button', { name: 'チームにお願いする', exact: true }).click()
  await page.waitForTimeout(600)
  const submit = page.locator('.ask button[type=submit]')
  await shot(page, 'network-1-sending', `POST /api/runs held open: main action reads "${(await submit.innerText()).trim()}", disabled=${await submit.isDisabled()}`)
  release()
  await page.waitForURL(/\/runs\//)
  await page.unrouteAll()

  const failing = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: 'ja-JP' })
  const fail = await failing.newPage()
  await fail.route('**/api/runs', (route) => route.request().method() === 'POST' ? route.abort('connectionfailed') : route.fallback())
  await fail.goto(base + '/', { waitUntil: 'networkidle' })
  await fail.locator('#request-goal').fill('この製品の紹介文を、分かりやすく作って。')
  await fail.getByRole('button', { name: 'チームにお願いする', exact: true }).click()
  await fail.locator('.ask [role=alert]').waitFor()
  await shot(fail, 'network-2-send-failed', 'POST /api/runs aborted: ' + (await fail.locator('.ask [role=alert]').innerText()).replace(/\s+/g, ' ').slice(0, 160))
  await shot(fail, 'network-3-send-failed-draft-kept', `after the failure the request text is still in the field: ${(await fail.locator('#request-goal').inputValue()).length} characters`)
  await failing.close()
  await context.close()
}

// 3. The work screen while its own data is slow, and when it cannot be reached.
{
  const runs = await (await fetch(`${base}/api/runs`)).json()
  const runId = runs[0].run_id
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: 'ja-JP' })
  const page = await context.newPage()
  let release
  await page.route(`**/api/runs/${runId}`, async (route) => { await new Promise((r) => { release = r }); await route.fallback() })
  const navigation = page.goto(`${base}/runs/${runId}`, { waitUntil: 'commit' })
  await page.waitForTimeout(1200)
  await shot(page, 'work-1-loading', 'GET the run held open: ' + (await page.locator('body').innerText()).replace(/\s+/g, ' ').slice(0, 120))
  release(); await navigation; await page.waitForTimeout(800)
  await page.unrouteAll()

  const offline = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: 'ja-JP' })
  const off = await offline.newPage()
  await off.route(`**/api/runs/${runId}`, (route) => route.abort('connectionfailed'))
  await off.goto(`${base}/runs/${runId}`, { waitUntil: 'commit' })
  // With no run to show, the screen keeps its own place and says why, with a way to try again.
  const said = off.locator('.simple-loading h1, .work-warning[role=alert]').first()
  await said.waitFor({ timeout: 30000 })
  await off.waitForTimeout(600)
  await shot(off, 'work-2-unreachable', 'GET the run aborted: ' + (await said.innerText()).replace(/\s+/g, ' ').slice(0, 160)
    + ' | retry offered: ' + await off.getByRole('button', { name: 'もう一度読み込む', exact: true }).isVisible())
  await offline.close()
  await context.close()
}

await browser.close()
writeFileSync(`${out}/capture.json`, JSON.stringify({ capturedAt: new Date().toISOString(), base,
  browser: 'Chrome (headless, channel=chrome)', motion: 'normal', locale: 'ja-JP',
  data: 'scripted TEST server; not real model output; not a real device',
  method: 'keyboard only for the journey shots; Playwright route interception for the network shots', shots }, null, 1))
for (const s of shots) console.log(s.file, s.horizontalOverflowPx > 1 ? `OVERFLOW ${s.horizontalOverflowPx}` : 'ok', '|', s.state.slice(0, 170))

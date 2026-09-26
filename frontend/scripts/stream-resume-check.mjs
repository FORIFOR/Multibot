// Regression check for the work screen's change stream and the inspector's file choice.
// Needs the scripted test server with pacing, e.g.:
//   cd backend && AGENTTEAM_ALLOW_FAKE_PROVIDER=1 AGENTTEAM_NO_SEATBELT=1 AGENTTEAM_FAKE_DELAY_MS=300 \
//     .venv/bin/python scripts/demo_fake_server.py --port 8791
// The scripted provider is test-only; this proves client behaviour, not model behaviour.
import { chromium } from 'playwright-core'
import assert from 'node:assert/strict'

const base = process.argv[2] || 'http://127.0.0.1:8791'
const only = process.argv[3] // optional: 'inspector'
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const results = {}
try {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 }, locale: 'ja-JP', reducedMotion: 'reduce' })
  const api = ctx.request
  const start = async (goal) => {
    const r = await api.post(`${base}/api/runs`, { data: { goal, inputs: { text: '', urls: [], files: [] } } })
    assert.ok(r.ok(), `create run: ${r.status()} ${await r.text()}`)
    return (await r.json()).run_id
  }
  const status = async (id) => (await (await api.get(`${base}/api/runs/${id}`)).json()).status
  const settled = ['completed', 'partial', 'failed', 'cancelled']

  const errors = []
  if (only !== 'inspector') {
  // 1. A live run: every stream starts after an already-loaded event, and only one is opened while it runs.
  const liveId = await start('ストリーム確認用: 製品の紹介文を作って')
  const page = await ctx.newPage()
  const streams = []
  page.on('pageerror', (e) => errors.push(e.message))
  page.on('request', (r) => { if (r.url().includes('/stream')) streams.push(new URL(r.url()).searchParams.get('after_seq')) })
  await page.goto(`${base}/runs/${liveId}`)
  for (let i = 0; i < 240 && !settled.includes(await status(liveId)); i++) await sleep(250)
  assert.ok(settled.includes(await status(liveId)), 'the paced run did not finish in time')
  await sleep(1500)
  assert.ok(streams.length >= 1, 'a live run opens the change stream')
  assert.ok(streams.every((s) => Number(s) > 0), `every stream resumes after a loaded event: ${streams}`)
  results.live = { streams }

  // 2. A finished run: returning to the tab does not reopen or replay the stream.
  const before = streams.length
  await page.reload()
  await page.getByRole('heading', { level: 1 }).waitFor()
  await sleep(1200)
  for (let i = 0; i < 3; i++) {
    await page.evaluate(() => { document.dispatchEvent(new Event('visibilitychange')); window.dispatchEvent(new Event('pageshow')) })
    await sleep(400)
  }
  const afterFinished = streams.slice(before)
  assert.deepEqual(afterFinished.filter((s) => Number(s) === 0), [], 'a finished run never replays from the first event')
  assert.ok(afterFinished.length <= 1, `a finished run does not reconnect on focus: ${afterFinished}`)
  results.finished = { streams: afterFinished }
  }

  // 3. The inspector keeps the file the reader chose while new events arrive.
  const inspectId = await start('選択保持の確認用: 製品の紹介文を作って')
  const p2 = await ctx.newPage()
  p2.on('pageerror', (e) => errors.push(e.message))
  await p2.goto(`${base}/runs/${inspectId}?tab=chat`)
  const files = p2.locator('.art-list button')
  for (let i = 0; i < 240 && (await files.count()) < 2; i++) await sleep(250)
  assert.ok((await files.count()) >= 2, 'at least two files were published while the run was live')
  const target = p2.locator('.art-list button[aria-pressed="false"]').first()
  const chosen = await target.locator('.path').textContent()
  await target.click()
  const seqBefore = (await (await api.get(`${base}/api/runs/${inspectId}`)).json()).last_seq
  for (let i = 0; i < 240 && !settled.includes(await status(inspectId)); i++) await sleep(250)
  await sleep(1500)
  const seqAfter = (await (await api.get(`${base}/api/runs/${inspectId}`)).json()).last_seq
  assert.ok(seqAfter > seqBefore, 'events arrived after the choice')
  const pressed = await p2.locator('.art-list button[aria-pressed="true"] .path').allTextContents()
  assert.deepEqual(pressed, [chosen], `the chosen file stays selected (chose ${chosen}, now ${pressed})`)
  results.inspector = { chosen, pressed, events_after_choice: seqAfter - seqBefore }

  assert.deepEqual(errors, [])
  console.log(JSON.stringify({ ok: true, ...results }))
} finally {
  await browser.close()
}

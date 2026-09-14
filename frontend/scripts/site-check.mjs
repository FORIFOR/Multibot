// Acceptance checks for the static site (docs/): finding→change jump, video events, mobile overflow, buttons, tracking.
import { chromium } from 'playwright-core'
const base = process.argv[2] || 'http://127.0.0.1:8799'
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const out = {}
for (const [name, path] of [['en', '/'], ['ja', '/ja/']]) {
  for (const [vp, w, h] of [['pc', 1440, 900], ['mobile', 390, 844]]) {
    const ctx = await browser.newContext({ viewport: { width: w, height: h } })
    const page = await ctx.newPage(); const errors = []
    page.on('pageerror', (e) => errors.push(String(e))); page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
    await page.goto(base + path, { waitUntil: 'networkidle' })
    const r = { errors }
    r.noHorizontalScroll = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)
    r.h1px = await page.evaluate(() => parseFloat(getComputedStyle(document.querySelector('h1')).fontSize))
    r.bodyPx = await page.evaluate(() => parseFloat(getComputedStyle(document.body).fontSize))
    r.btnMinH = await page.evaluate(() => Math.min(...[...document.querySelectorAll('.btn')].map((b) => b.getBoundingClientRect().height)))
    r.recordAboveFold = await page.evaluate(() => { const el = document.querySelector('#record .art'); return el ? el.getBoundingClientRect().top < window.innerHeight : false })
    // finding → change jump
    r.jumps = []
    for (const id of ['F-1', 'F-2', 'F-3']) {
      await page.click(`.finding[data-id="${id}"]`); await page.waitForTimeout(700)
      r.jumps.push(await page.evaluate((id) => { const hit = document.querySelector('.blk.hit'); const b = hit.getBoundingClientRect(); const on = document.querySelector('.finding.on'); return { id, target: hit.dataset.fix, visible: b.bottom > 0 && b.top < window.innerHeight, on: on && on.dataset.id } }, id))
    }
    // events
    r.events = await page.evaluate(() => (window.dataLayer || []).map((e) => e.event))
    r.videoPoster = await page.evaluate(() => !!document.querySelector('#replay-video').poster && document.querySelector('#replay-video').autoplay === false)
    r.videoEvents = await page.evaluate(async () => { const v = document.getElementById('replay-video'); v.muted = true; try { await v.play() } catch (e) {} await new Promise((r) => { if (v.readyState >= 1) r(); else v.addEventListener('loadedmetadata', r, { once: true }) }); v.currentTime = Math.max(0, v.duration - 0.2); await new Promise((r) => { const t = setTimeout(r, 6000); v.addEventListener('ended', () => { clearTimeout(t); r() }, { once: true }) }); return (window.dataLayer || []).filter((e) => e.kind === 'replay').map((e) => e.event) })
    r.brand = await page.evaluate(() => /Agent Team/.test(document.querySelector('.brand').textContent) && /Multibot/.test(document.querySelector('.brand').textContent) && /MIT/.test(document.querySelector('footer').textContent) && !!document.querySelector('a[href="https://github.com/FORIFOR/Multibot"]'))
    r.leadForm = await page.evaluate(() => !!document.querySelector('#portfolio-form button[type="submit"]'))
    r.quickstart = await page.evaluate(() => !!document.querySelector('#github .term'))
    out[`${name}-${vp}`] = r
    await ctx.close()
  }
}
await browser.close()
console.log(JSON.stringify(out, null, 1))

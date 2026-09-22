// Acceptance checks for the static site (docs/): first screen, character stage, real findings, mobile overflow, no-JS and reduced motion.
// Nothing here calls a model; the page itself never does either.
import { chromium, webkit } from 'playwright-core'
const base = process.argv[2] || 'http://127.0.0.1:8799'
// BROWSER=webkit checks the Safari engine (install once: node node_modules/playwright-core/cli.js install webkit).
const browser = process.env.BROWSER === 'webkit' ? await webkit.launch({ headless: true }) : await chromium.launch({ channel: 'chrome', headless: true })
const out = {}; const failures = []
const expect = (key, name, ok, detail) => { if (!ok) failures.push(`${key}: ${name}${detail === undefined ? '' : ' → ' + JSON.stringify(detail)}`) }
for (const [name, path] of [['en', '/'], ['ja', '/ja/']]) {
  for (const [vp, w, h] of [['pc', 1440, 900], ['tablet', 768, 1024], ['mobile', 390, 844], ['small', 360, 740]]) {
    const key = `${name}-${vp}`
    const ctx = await browser.newContext({ viewport: { width: w, height: h } })
    const page = await ctx.newPage(); const errors = []
    page.on('pageerror', (e) => errors.push(String(e))); page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
    await page.goto(base + path, { waitUntil: 'networkidle' })
    const r = { errors }
    r.noHorizontalScroll = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)
    r.h1Count = await page.locator('h1').count()
    r.h1px = await page.evaluate(() => parseFloat(getComputedStyle(document.querySelector('h1')).fontSize))
    r.bodyPx = await page.evaluate(() => parseFloat(getComputedStyle(document.body).fontSize))
    r.btnMinH = await page.evaluate(() => Math.min(...[...document.querySelectorAll('.btn')].map((b) => b.getBoundingClientRect().height)))
    // The fold now carries the recording of a real run instead of an explanatory animation: it must be visible
    // there, it must not start on its own, and it must be understandable without sound.
    const demo = await page.evaluate(() => {
      const v = document.querySelector('#demo-video')
      if (!v) return null
      const r = v.getBoundingClientRect()
      return { onFold: r.top < window.innerHeight, visiblePx: Math.round(Math.min(innerHeight, r.bottom) - Math.max(0, r.top)),
               poster: !!v.getAttribute('poster'), autoplay: v.autoplay, controls: v.controls, muted: v.muted,
               preload: v.getAttribute('preload'), tracks: v.textTracks.length, playedOnItsOwn: v.currentTime > 0 }
    })
    r.demoOnFold = !!demo && demo.onFold && demo.visiblePx > 180
    r.demoHasPoster = !!demo && demo.poster
    r.demoDoesNotAutoplay = !!demo && !demo.autoplay && !demo.playedOnItsOwn
    r.demoCaptioned = !!demo && demo.tracks > 0
    r.demoIsControllable = !!demo && demo.controls && demo.muted
    r.demoDefersBytes = !!demo && demo.preload === 'none'
    // One primary action in the fold; the record link stays a quiet link.
    r.onePrimaryCta = await page.evaluate(() => document.querySelectorAll('.hero .btn').length === 1)
    // Each real finding shows its own recorded before/after, and only that one.
    r.findings = []
    for (const i of [0, 1, 2]) {
      await page.click(`[data-finding="${i}"]`)
      r.findings.push(await page.evaluate((i) => ({ pressed: document.querySelector(`[data-finding="${i}"]`).getAttribute('aria-pressed'), visible: [...document.querySelectorAll('[data-diff]')].filter((d) => !d.hidden).map((d) => d.dataset.diff) }), i))
    }
    // Real app screens: one visible at a time, arrow keys move between them, images have intrinsic size (no layout shift).
    await page.click('[data-shot="1"]'); await page.keyboard.press('ArrowRight')
    r.shots = await page.evaluate(() => ({ visible: [...document.querySelectorAll('[data-shot-panel]')].filter((p) => !p.hidden).map((p) => p.dataset.shotPanel), selected: [...document.querySelectorAll('[data-shot][aria-selected="true"]')].map((t) => t.dataset.shot), sized: [...document.querySelectorAll('.shot img')].every((i) => i.getAttribute('width') && i.getAttribute('height') && i.alt) }))
    r.shotLoaded = await page.evaluate(async () => { const i = document.querySelector('[data-shot-panel]:not([hidden]) img'); if (!i.complete) await new Promise((r) => { i.onload = r; i.onerror = r }); return i.naturalWidth > 0 })
    r.noAutoplayMedia = await page.evaluate(() => [...document.querySelectorAll('video,audio')].every((m) => !m.autoplay))
    r.brand = await page.evaluate(() => /Agent Team/.test(document.querySelector('.brand').textContent) && /Multibot/.test(document.querySelector('.brand').textContent) && /MIT/.test(document.querySelector('footer').textContent) && !!document.querySelector('a[href="https://github.com/FORIFOR/Multibot"]'))
    r.leadForm = await page.evaluate(() => !!document.querySelector('#portfolio-form button[type="submit"]') && !!document.querySelector('#portfolio-form input[name="consent"][required]'))
    r.quickstart = await page.evaluate(() => /agentteam quickstart/.test(document.querySelector('#github.term').textContent))
    r.evidenceLinks = await page.evaluate(() => [...document.querySelectorAll('a[href*="/docs/evidence/"]')].length)
    out[key] = r
    expect(key, 'no console/page errors', errors.length === 0, errors); expect(key, 'no horizontal scroll', r.noHorizontalScroll)
    expect(key, 'one h1', r.h1Count === 1, r.h1Count); expect(key, 'body text ≥ 16px', r.bodyPx >= 16, r.bodyPx); expect(key, 'buttons ≥ 48px', r.btnMinH >= 48, r.btnMinH)
    expect(key, 'the recording is on the first screen', r.demoOnFold)
    expect(key, 'the recording has a poster', r.demoHasPoster)
    expect(key, 'the recording does not start on its own', r.demoDoesNotAutoplay)
    expect(key, 'the recording is captioned', r.demoCaptioned)
    expect(key, 'the recording is muted and controllable', r.demoIsControllable)
    expect(key, 'the recording defers its bytes', r.demoDefersBytes)
    expect(key, 'one primary action in the fold', r.onePrimaryCta)
    r.findings.forEach((f, i) => expect(key, `finding ${i} shows only its diff`, f.pressed === 'true' && f.visible.length === 1 && f.visible[0] === String(i), f))
    expect(key, 'app screens: tab 3 after click + ArrowRight', r.shots.visible.join() === '2' && r.shots.selected.join() === '2' && r.shots.sized && r.shotLoaded, r.shots)
    expect(key, 'brand, MIT, repo link', r.brand); expect(key, 'inquiry form with consent', r.leadForm); expect(key, 'quickstart command', r.quickstart); expect(key, 'evidence links', r.evidenceLinks >= 2, r.evidenceLinks)
    await ctx.close()
  }
  // Reduced motion: no loop, everyone shown as finished. No JavaScript: every section still readable.
  const calm = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' }); const cp = await calm.newPage()
  await cp.goto(base + path, { waitUntil: 'networkidle' }); await cp.waitForTimeout(2500)
  // Under reduced motion the recording still must not start by itself, and every section stays visible.
  const still = await cp.evaluate(() => { const v = document.querySelector('#demo-video'); return !!v && v.paused && v.currentTime === 0 })
  const revealed = await cp.evaluate(() => [...document.querySelectorAll('[data-reveal]')].every((el) => getComputedStyle(el).opacity === '1'))
  out[`${name}-reduced-motion`] = { still, revealed }; expect(`${name}-reduced-motion`, 'the recording stays still and content is visible', still && revealed); await calm.close()
  const plain = await browser.newContext({ viewport: { width: 1440, height: 900 }, javaScriptEnabled: false }); const pp = await plain.newPage()
  await pp.goto(base + path, { waitUntil: 'load' })
  const readable = await pp.evaluate(() => [...document.querySelectorAll('[data-reveal]')].every((el) => getComputedStyle(el).opacity === '1') && !![...document.querySelectorAll('[data-diff]')].find((d) => !d.hidden) && !!document.querySelector('#demo-video[poster]') && [...document.querySelectorAll('[data-shot-panel]')].every((p) => p.getBoundingClientRect().height > 100))
  out[`${name}-no-js`] = { readable }; expect(`${name}-no-js`, 'readable without JavaScript', readable); await plain.close()
}
await browser.close()
console.log(JSON.stringify({ ok: failures.length === 0, failures, out }, null, 1))
process.exit(failures.length ? 1 : 0)

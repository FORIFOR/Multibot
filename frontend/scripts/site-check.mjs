// Acceptance checks for the static site (docs/): first screen, character stage, real findings, mobile overflow, no-JS and reduced motion.
// Nothing here calls a model; the page itself never does either.
import { chromium } from 'playwright-core'
const base = process.argv[2] || 'http://127.0.0.1:8799'
const browser = await chromium.launch({ channel: 'chrome', headless: true })
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
    r.teamAboveFold = await page.evaluate(() => document.querySelector('.mate .bot-character').getBoundingClientRect().top < window.innerHeight)
    // The stage is an explanation that moves through the hand-off, and the visitor can stop it.
    const pills = () => page.locator('[data-pill]').allTextContents()
    const first = await pills(); await page.waitForTimeout(2400); const second = await pills()
    r.stageMoves = JSON.stringify(first) !== JSON.stringify(second)
    await page.click('#stage-toggle'); const held = await pills(); await page.waitForTimeout(2600)
    r.stagePauses = JSON.stringify(held) === JSON.stringify(await pills()) && await page.getAttribute('#stage-toggle', 'aria-pressed') === 'true'
    // Each real finding shows its own recorded before/after, and only that one.
    r.findings = []
    for (const i of [0, 1, 2]) {
      await page.click(`[data-finding="${i}"]`)
      r.findings.push(await page.evaluate((i) => ({ pressed: document.querySelector(`[data-finding="${i}"]`).getAttribute('aria-pressed'), visible: [...document.querySelectorAll('[data-diff]')].filter((d) => !d.hidden).map((d) => d.dataset.diff) }), i))
    }
    r.noAutoplayMedia = await page.evaluate(() => [...document.querySelectorAll('video,audio')].every((m) => !m.autoplay))
    r.brand = await page.evaluate(() => /Agent Team/.test(document.querySelector('.brand').textContent) && /Multibot/.test(document.querySelector('.brand').textContent) && /MIT/.test(document.querySelector('footer').textContent) && !!document.querySelector('a[href="https://github.com/FORIFOR/Multibot"]'))
    r.leadForm = await page.evaluate(() => !!document.querySelector('#portfolio-form button[type="submit"]') && !!document.querySelector('#portfolio-form input[name="consent"][required]'))
    r.quickstart = await page.evaluate(() => /agentteam quickstart/.test(document.querySelector('#github.term').textContent))
    r.evidenceLinks = await page.evaluate(() => [...document.querySelectorAll('a[href*="/docs/evidence/"]')].length)
    out[key] = r
    expect(key, 'no console/page errors', errors.length === 0, errors); expect(key, 'no horizontal scroll', r.noHorizontalScroll)
    expect(key, 'one h1', r.h1Count === 1, r.h1Count); expect(key, 'body text ≥ 16px', r.bodyPx >= 16, r.bodyPx); expect(key, 'buttons ≥ 48px', r.btnMinH >= 48, r.btnMinH)
    if (vp === 'pc') expect(key, 'team visible on the first screen', r.teamAboveFold)
    expect(key, 'stage moves', r.stageMoves); expect(key, 'stage pauses', r.stagePauses)
    r.findings.forEach((f, i) => expect(key, `finding ${i} shows only its diff`, f.pressed === 'true' && f.visible.length === 1 && f.visible[0] === String(i), f))
    expect(key, 'brand, MIT, repo link', r.brand); expect(key, 'inquiry form with consent', r.leadForm); expect(key, 'quickstart command', r.quickstart); expect(key, 'evidence links', r.evidenceLinks >= 2, r.evidenceLinks)
    await ctx.close()
  }
  // Reduced motion: no loop, everyone shown as finished. No JavaScript: every section still readable.
  const calm = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' }); const cp = await calm.newPage()
  await cp.goto(base + path, { waitUntil: 'networkidle' }); const a = await cp.locator('[data-pill]').allTextContents(); await cp.waitForTimeout(2500)
  const still = JSON.stringify(a) === JSON.stringify(await cp.locator('[data-pill]').allTextContents()) && new Set(a).size === 1
  const revealed = await cp.evaluate(() => [...document.querySelectorAll('[data-reveal]')].every((el) => getComputedStyle(el).opacity === '1'))
  out[`${name}-reduced-motion`] = { still, revealed }; expect(`${name}-reduced-motion`, 'stage is static and content is visible', still && revealed); await calm.close()
  const plain = await browser.newContext({ viewport: { width: 1440, height: 900 }, javaScriptEnabled: false }); const pp = await plain.newPage()
  await pp.goto(base + path, { waitUntil: 'load' })
  const readable = await pp.evaluate(() => [...document.querySelectorAll('[data-reveal]')].every((el) => getComputedStyle(el).opacity === '1') && !![...document.querySelectorAll('[data-diff]')].find((d) => !d.hidden) && document.querySelector('#stage-toggle').hidden)
  out[`${name}-no-js`] = { readable }; expect(`${name}-no-js`, 'readable without JavaScript', readable); await plain.close()
}
await browser.close()
console.log(JSON.stringify({ ok: failures.length === 0, failures, out }, null, 1))
process.exit(failures.length ? 1 : 0)

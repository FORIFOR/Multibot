// Automated accessibility scan (axe, WCAG 2.x A/AA) of the everyday screens, against the scripted TEST server.
// Zero findings here is not conformance: keyboard operation, focus order and screen-reader output need a person.
//   BASE=http://127.0.0.1:8791 node scripts/a11y-smoke.mjs
import { chromium } from 'playwright-core'
import { AxeBuilder } from '@axe-core/playwright'
const base = process.env.BASE || 'http://127.0.0.1:8791'
// A stalled scan must fail loudly instead of hanging CI.
const watchdog = setTimeout(() => { console.error('a11y-smoke: timed out after 240s'); process.exit(2) }, 240000)
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const report = []; let failed = false
try {
  for (const [lang, locale] of [['ja', 'ja-JP'], ['en', 'en-US']]) for (const [width, height] of [[1440, 900], [390, 844]]) {
    const context = await browser.newContext({ viewport: { width, height }, locale, reducedMotion: 'reduce' })
    const page = await context.newPage()
    await page.addInitScript(l => { try { localStorage.setItem('agentteam.lang', l) } catch { /* ignore */ } }, lang)
    const scan = async (name) => {
      // The deliverable preview is a sandboxed iframe with generated content: axe cannot enter it (it waits forever), and its
      // content is the team's output, not this UI. It is excluded here and stays a manual check.
      const result = await new AxeBuilder({ page }).exclude('.result-reader iframe').withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']).analyze()
      const findings = result.violations.map(v => ({ id: v.id, impact: v.impact, nodes: v.nodes.length, first: v.nodes[0]?.target?.join(' '), help: v.help }))
      report.push({ screen: name, lang, width, findings }); if (findings.length) failed = true
    }
    await page.goto(base, { waitUntil: 'networkidle' }); await scan('home')
    await page.goto(base + '/welcome', { waitUntil: 'networkidle' }); await scan('welcome')
    await page.goto(base + '/settings', { waitUntil: 'networkidle' }); await scan('my-team')
    await page.goto(base, { waitUntil: 'networkidle' })
    await page.locator('#request-goal').fill(lang === 'ja' ? '紹介文を作って' : 'Write a short introduction')
    await scan('home-request-written')  // the main button is only enabled, and only then checked for contrast, once a request is written
    await page.locator('form.ask button[type=submit]').click(); await page.waitForURL(/\/runs\//)
    await page.locator('.result-reader').waitFor({ timeout: 60000 }); await page.waitForTimeout(600); await scan('work-screen')
    await context.close()
  }
} finally { await browser.close() }
console.log(JSON.stringify({ ok: !failed, screens: report.length, findings: report.filter(r => r.findings.length) }, null, 1))
clearTimeout(watchdog)
process.exit(failed ? 1 : 0)

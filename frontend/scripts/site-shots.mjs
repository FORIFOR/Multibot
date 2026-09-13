import { chromium } from 'playwright-core'
const [,, base, out, ...pages] = process.argv
const browser = await chromium.launch({ channel: 'chrome', headless: true })
for (const spec of pages) {
  const [path, name, w = '1440', h = '900', full = '0', click = ''] = spec.split('|')
  const ctx = await browser.newContext({ viewport: { width: +w, height: +h }, deviceScaleFactor: 1 })
  const page = await ctx.newPage(); await page.goto(base + path, { waitUntil: 'networkidle' }); await page.waitForTimeout(600)
  if (click) { await page.click(click); await page.waitForTimeout(1200) }
  await page.screenshot({ path: `${out}/${name}.png`, fullPage: full === '1' }); await ctx.close(); console.log('shot', name)
}
await browser.close()

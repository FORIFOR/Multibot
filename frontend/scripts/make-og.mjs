// Builds the share images from the page's own words and the current recording, so a shared link shows what the page
// actually says. Run after build_site.py.   node frontend/scripts/make-og.mjs <siteBase>
import { chromium } from 'playwright-core'
const base = process.argv[2] || 'http://127.0.0.1:8123'
const out = new URL('../../docs/media', import.meta.url).pathname
const b = await chromium.launch({ channel: 'chrome', headless: true })
for (const [lang, path, file, poster] of [['ja', 'ja/', 'og-ja.png', 'demo-poster-ja.jpg'], ['en', '', 'og.png', 'demo-poster.jpg']]) {
  const ctx = await b.newContext({ viewport: { width: 1200, height: 630 }, locale: lang === 'ja' ? 'ja-JP' : 'en-US', deviceScaleFactor: 2 })
  const p = await ctx.newPage()
  await p.goto(base + '/' + path, { waitUntil: 'networkidle' })
  const words = await p.evaluate(() => ({ h1: document.querySelector('h1').innerText.replace(/\s+/g, ' '), lede: document.querySelector('.hero .lede').innerText.replace(/\s+/g, ' ') }))
  await ctx.close()
  const card = await b.newPage({ viewport: { width: 1200, height: 630 }, deviceScaleFactor: 2 })
  await card.setContent(`<!doctype html><meta charset="utf-8"><style>
    html,body{margin:0;height:100%}
    body{display:grid;grid-template-rows:auto 1fr;gap:0;background:#f5f5f5;font-family:'Hiragino Sans','Inter',sans-serif;color:#0a0a0a}
    .top{padding:52px 60px 0}
    .brand{display:flex;align-items:center;gap:10px;font-size:22px;font-weight:600;letter-spacing:-.02em}
    .brand i{width:18px;height:18px;border-radius:6px;background:#0a0a0a;display:inline-block}
    h1{margin:22px 0 12px;font-size:${lang === 'ja' ? 46 : 44}px;font-weight:800;letter-spacing:-.04em;line-height:1.24;max-width:16em}
    p{margin:0;font-size:19px;line-height:1.7;color:#666;max-width:34em}
    .shot{margin:26px 60px 0;height:100%;border-radius:18px 18px 0 0;border:1px solid #e5e5e5;border-bottom:0;background:#fff url('${base}/media/${poster}') top center/cover no-repeat}
  </style>
  <div class="top"><span class="brand"><i></i>Agent Team</span><h1>${words.h1}</h1><p>${words.lede}</p></div><div class="shot"></div>`)
  await card.waitForTimeout(900)
  await card.screenshot({ path: `${out}/${file}` })
  console.log('wrote', file, '—', words.h1.slice(0, 40))
  await card.close()
}
await b.close()

// Renders caption strips and the end card as PNGs, so the edit can burn them in without a text-capable ffmpeg build.
//   node frontend/scripts/make-captions.mjs <outDir> <captions.json>
import { chromium } from 'playwright-core'
import { readFileSync } from 'node:fs'
const [out, spec] = process.argv.slice(2)
const items = JSON.parse(readFileSync(spec, 'utf8'))
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const page = await browser.newPage({ viewport: { width: 1280, height: 400 }, deviceScaleFactor: 2 })
for (const item of items) {
  const w = item.width || 1280
  if (item.kind === 'card') {
    await page.setViewportSize({ width: w, height: item.height || 800 })
    await page.setContent(`<!doctype html><meta charset="utf-8"><style>
      html,body{margin:0;height:100%}
      body{display:grid;place-items:center;background:#f5f5f5;font-family:'Hiragino Sans','Hiragino Kaku Gothic ProN',sans-serif;color:#0a0a0a}
      .card{display:grid;gap:22px;justify-items:center;text-align:center;padding:0 60px}
      h1{margin:0;font-size:${Math.round(w / 22)}px;font-weight:700;letter-spacing:-.04em;line-height:1.25}
      code{font-family:'SFMono-Regular',ui-monospace,monospace;font-size:${Math.round(w / 72)}px;word-break:keep-all;overflow-wrap:break-word;max-width:${w - 140}px;text-align:left;line-height:1.6;background:#fff;border:1px solid #e5e5e5;border-radius:12px;padding:14px 20px}
      p{margin:0;font-size:${Math.round(w / 46)}px;color:#666}
    </style><div class="card"><h1>${item.title}</h1><code>${item.code}</code><p>${item.note}</p></div>`)
  } else {
    await page.setViewportSize({ width: w, height: item.height || 200 })
    await page.setContent(`<!doctype html><meta charset="utf-8"><style>
      html,body{margin:0}
      body{display:flex;align-items:flex-end;justify-content:center;height:${item.height || 200}px;background:transparent;
           font-family:'Hiragino Sans','Hiragino Kaku Gothic ProN',sans-serif}
      .bar{max-width:${w - 80}px;margin:0 0 ${item.bottom || 28}px;padding:${item.pad || '16px 26px'};border-radius:14px;
           background:rgba(10,10,10,.86);color:#fff;font-size:${item.size || 34}px;font-weight:600;line-height:1.5;letter-spacing:.01em;text-align:center}
      .sub{display:block;margin-top:6px;font-size:${Math.round((item.size || 34) * 0.62)}px;font-weight:500;color:#d4d4d4}
    </style><div class="bar">${item.text}${item.sub ? `<span class="sub">${item.sub}</span>` : ''}</div>`)
  }
  await page.waitForTimeout(120)
  await page.screenshot({ path: `${out}/${item.name}.png`, omitBackground: item.kind !== 'card' })
  console.log('rendered', item.name)
}
await browser.close()

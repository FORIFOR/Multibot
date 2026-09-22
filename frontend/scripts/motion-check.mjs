// Measures the motion contract (docs/design/acceptance.md 5) instead of watching it: under prefers-reduced-motion and
// under the work screen's own "動きを止める", nothing that is not essential is still moving.
//   UI_BASE_URL=http://127.0.0.1:8791 node frontend/scripts/motion-check.mjs
//
// What it looks at, after the first round of this check was found too narrow:
//   - document.getAnimations(), so CSS animations, CSS transitions and element.animate() are all covered
//   - elements in fixed position and inside shadow roots, which an offsetParent test skips
//   - every duration in a list ("opacity 0s, transform .3s" counts as moving), and transition-property: all
//   - scroll-behavior on scrollable containers, because a smooth programmatic scroll is motion too
//   - what a scrollIntoView asks for while paused, because a CSS class cannot reach a scroll asked for in script
// What it still cannot see, and why: a script that sets scrollTop directly moves content with no animation to find
// (the conversation follows new messages that way, TeamConversation.tsx:17). That one is listed under
// knownExclusions, not silently dropped.
import { chromium } from 'playwright-core'
import { mkdirSync, writeFileSync } from 'node:fs'

const base = process.env.UI_BASE_URL || 'http://127.0.0.1:8791'
const out = new URL('../../artifacts/ui', import.meta.url).pathname
mkdirSync(out, { recursive: true })
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const runId = (await (await fetch(`${base}/api/runs`)).json())[0].run_id

const moving = (page) => page.evaluate(() => {
  const describe = (el) => {
    if (!(el instanceof Element)) return String(el)
    const cls = el.getAttribute?.('class')
    return `${el.tagName.toLowerCase()}${cls ? '.' + cls.trim().split(/\s+/).slice(0, 2).join('.') : ''}`
  }
  const found = []
  // 1. Everything the browser itself considers animating: CSS animations, CSS transitions, script animations.
  for (const animation of document.getAnimations()) {
    if (animation.playState !== 'running') continue
    const timing = animation.effect?.getTiming?.() || {}
    const duration = typeof timing.duration === 'number' ? timing.duration : 0
    if (!duration && !timing.iterations) continue
    found.push({ kind: animation.constructor.name, name: animation.animationName || animation.transitionProperty || '(script)',
                 target: describe(animation.effect?.target), duration, playState: animation.playState })
  }
  // 2. Declared transitions that are simply waiting for their trigger: a hover or a state change would move them.
  const roots = [document]
  const elements = []
  while (roots.length) {
    const root = roots.pop()
    for (const el of root.querySelectorAll('*')) {
      if (el.shadowRoot) roots.push(el.shadowRoot)
      elements.push(el)
    }
  }
  for (const el of elements) {
    if (!(el instanceof HTMLElement) || !el.checkVisibility?.({ checkOpacity: false, checkVisibilityCSS: true })) continue
    const style = getComputedStyle(el)
    const longest = (value) => Math.max(0, ...String(value).split(',').map((part) => {
      const seconds = parseFloat(part)
      return Number.isFinite(seconds) ? (part.includes('ms') ? seconds / 1000 : seconds) : 0
    }))
    if (style.transitionProperty !== 'none' && longest(style.transitionDuration) > 0) {
      found.push({ kind: 'declared transition', name: style.transitionProperty, target: describe(el),
                   duration: longest(style.transitionDuration) * 1000, playState: 'idle (waits for a trigger)' })
    }
    if (style.animationName !== 'none' && style.animationPlayState === 'running' && longest(style.animationDuration) > 0) {
      found.push({ kind: 'declared animation', name: style.animationName, target: describe(el),
                   duration: longest(style.animationDuration) * 1000, playState: style.animationPlayState })
    }
    if (style.scrollBehavior === 'smooth' && (el.scrollHeight > el.clientHeight || el.scrollWidth > el.clientWidth)) {
      found.push({ kind: 'smooth scrolling container', name: 'scroll-behavior: smooth', target: describe(el), duration: null, playState: 'n/a' })
    }
  }
  return found
})

const screens = [['ask', '/'], ['work', `/runs/${runId}`], ['my team', '/settings'], ['work list', '/runs'], ['welcome', '/welcome']]
const cases = []
for (const reduced of [false, true]) {
  for (const [width, height] of [[1440, 900], [390, 844]]) {
    for (const [name, path] of screens) {
      const context = await browser.newContext({ viewport: { width, height }, locale: 'ja-JP', reducedMotion: reduced ? 'reduce' : 'no-preference' })
      const page = await context.newPage()
      await page.goto(base + path, { waitUntil: 'networkidle' })
      await page.waitForTimeout(900)
      cases.push({ screen: name, viewport: `${width}x${height}`, reducedMotion: reduced, paused: false, moving: await moving(page) })
      // The work screen carries the "動きを止める" control; press it and measure the same screen again.
      if (name === 'work') {
        const summary = page.locator('.work-progress-disclosure > summary')
        if (await summary.count()) await summary.click()
        const pause = page.getByRole('button', { name: '動きを止める', exact: true })
        if (await pause.count()) {
          await pause.click()
          await page.waitForTimeout(500)
          cases.push({ screen: name, viewport: `${width}x${height}`, reducedMotion: reduced, paused: true, moving: await moving(page) })
          // A scroll asked for in script never touches CSS, so the class cannot stop it. Record what it asks for.
          await page.evaluate(() => {
            window.__scrolls = []
            const original = Element.prototype.scrollIntoView
            Element.prototype.scrollIntoView = function (options) { window.__scrolls.push(options?.behavior ?? 'default'); return original.call(this, options) }
          })
          const tab = page.locator('.room-view-nav button').nth(1)
          if (await tab.count()) { await tab.click(); await page.waitForTimeout(400) }
          const asked = await page.evaluate(() => window.__scrolls)
          cases.push({ screen: name, viewport: `${width}x${height}`, reducedMotion: reduced, paused: true,
                       action: 'switched panel while paused', scrollBehaviour: asked, moving: await moving(page) })
        }
      }
      await context.close()
    }
  }
}
await browser.close()

const essential = (entry) => /processing-dots|pulse|activity-mark|spin/i.test(`${entry.name} ${entry.target}`)
const summary = {
  measuredAt: new Date().toISOString(), base, browser: 'Chrome (headless, channel=chrome)',
  method: 'document.getAnimations() plus computed transition/animation/scroll-behavior over every visible element, including fixed position and shadow roots; all durations in a list are read, and transition-property: all counts',
  basis: 'docs/design/acceptance.md 5 — non-essential motion stops under reduced motion and under 動きを止める; regular motion is checked separately',
  note: 'a measurement of what the browser would animate. It is not a person watching the screen and not a real device.',
  knownExclusions: ['content moved by script with no animation to find: the conversation follows new messages by setting scrollTop (frontend/src/components/TeamConversation.tsx:17). A scroll asked for through scrollIntoView IS covered: scrollBehaviour records what the panel switch requests while paused.'],
  cases: cases.map((c) => ({ ...c, movingCount: c.moving.length, essentialCount: c.moving.filter(essential).length })),
}
writeFileSync(`${out}/motion.json`, JSON.stringify(summary, null, 1))
let quiet = true
for (const c of summary.cases) {
  const label = `${c.screen} ${c.viewport} reduced=${c.reducedMotion} paused=${c.paused}`
  if ((c.reducedMotion || c.paused) && c.movingCount > 0) quiet = false
  if (c.scrollBehaviour && c.scrollBehaviour.some((b) => b === 'smooth')) quiet = false
  console.log(`${label} | moving: ${c.movingCount}`, c.moving.slice(0, 3).map((m) => `${m.kind}:${m.name}@${m.target}`).join(' , '))
}
console.log(quiet ? 'QUIET: nothing moves under reduced motion or while paused' : 'STILL MOVING under reduced motion or while paused')
if (!quiet) process.exitCode = 1

import {chromium} from 'playwright-core'
import AxeBuilder from '@axe-core/playwright'
import assert from 'node:assert/strict'
import {writeFileSync} from 'node:fs'
const b=await chromium.launch({channel:'chrome',headless:true}),results=[]
try{for(const width of [1440,390]){const context=await b.newContext({viewport:{width,height:1000},reducedMotion:'reduce'});const p=await context.newPage();await p.goto('http://127.0.0.1:8798/runs/run_1a09c8485503d406bf4');await p.locator('.conversation-message').waitFor();await p.evaluate(()=>scrollTo(0,0));const r=await new AxeBuilder({page:p}).include('.work-progress').include('.live-conversation').withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();results.push({width,violations:r.violations});await p.screenshot({path:`../artifacts/product-quality/workroom-live/review-${width}.png`,fullPage:true});await context.close()};writeFileSync('../artifacts/product-quality/workroom-live/a11y.json',JSON.stringify(results,null,2));assert.ok(results.every(r=>!r.violations.length));console.log('PASS scoped axe, 1440/390')}finally{await b.close()}

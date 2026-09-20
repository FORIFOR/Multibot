import {chromium} from 'playwright-core';
import {readFileSync,writeFileSync} from 'node:fs';
import assert from 'node:assert/strict';
const out=process.env.QUALITY_OUT || '../artifacts/product-quality/completion';
const runId=readFileSync(`${out}/run-id.txt`,'utf8').trim();
const base=process.env.QUALITY_BASE || 'http://127.0.0.1:8799';
const browser=await chromium.launch({channel:'chrome'});
try {
 const ctx=await browser.newContext({locale:'ja-JP',viewport:{width:1440,height:1000},acceptDownloads:true,reducedMotion:'reduce'});
 const p=await ctx.newPage();const errors=[];p.on('pageerror',e=>errors.push(e.message));
 const before=await(await ctx.request.get(`${base}/api/runs/${runId}`)).json();
 assert.equal(before.status,'completed');
 await p.goto(`${base}/runs/${runId}?view=deliverables`);
 await p.locator('.result-reader').waitFor();
 if(await p.locator('[data-adopt]').count()){await p.locator('[data-adopt]').focus();await p.keyboard.press('Enter');}
 await p.locator('.chosen-pill').waitFor();
 const downloaded=p.waitForEvent('download');
 await p.getByRole('link',{name:'採用したファイルを保存'}).click();
 await(await downloaded).saveAs(`${out}/selected-browser.zip`);
 await p.reload();await p.locator('.chosen-pill').waitFor();
 const after=await(await ctx.request.get(`${base}/api/runs/${runId}`)).json();
 const expected=before.artifacts.at(-1);
 assert.equal(after.artifact_selection[expected.artifact_id].revision,expected.revision);
 assert.equal(after.artifacts.find(a=>a.artifact_id===expected.artifact_id&&a.revision===after.artifact_selection[expected.artifact_id].revision).sha256,expected.sha256);
 writeFileSync(`${out}/selected-run.json`,JSON.stringify(after,null,2));
 await p.screenshot({path:`${out}/final-desktop.png`,fullPage:true});
 await p.setViewportSize({width:390,height:844});
 const sizes=await p.evaluate(()=>({viewport:innerWidth,width:document.documentElement.scrollWidth}));
 assert.ok(sizes.width<=sizes.viewport+1);
 await p.screenshot({path:`${out}/final-mobile.png`,fullPage:true});
 assert.deepEqual(errors,[]);
 writeFileSync(`${out}/download-observation.json`,JSON.stringify({browser:browser.version(),runId,adoptionPersisted:true,sizes,errors},null,2));
 console.log('Browser selected exact revision, persisted across reload, downloaded ZIP; mobile no overflow.');
} finally {await browser.close();}

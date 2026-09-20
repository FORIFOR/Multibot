import {chromium} from 'playwright-core';
import {readFileSync, writeFileSync} from 'node:fs';
import assert from 'node:assert/strict';
const out='../artifacts/product-quality/trading-team-round2';
const base='http://127.0.0.1:8802', id=readFileSync(`${out}/run-id.txt`,'utf8').trim();
const browser=await chromium.launch({channel:'chrome'});
try {
  const context=await browser.newContext({locale:'ja-JP',viewport:{width:1440,height:1000}});
  const page=await context.newPage();
  const events=await(await context.request.get(`${base}/api/runs/${id}/events`)).json();
  const run=await(await context.request.get(`${base}/api/runs/${id}`)).json();
  const review=events.find(e=>e.type==='review.submitted'&&e.payload.results.some(r=>r.status==='fail'));
  assert.ok(review,'Requires an actual failed review');
  const ref=review.payload.target_artifacts[0];
  const file=run.artifacts.find(f=>f.artifact_id===ref.artifact_id&&f.revision===ref.revision&&f.sha256===ref.sha256);
  assert.ok(file,'Requires the same published revision');
  await page.goto(`${base}/runs/${id}?view=deliverables`);
  const button=page.locator('.result-file-list button').filter({hasText:file.logical_path});
  await button.click();
  await page.getByRole('region',{name:`成果物：${file.logical_path}`,exact:true}).waitFor();
  await page.getByRole('button',{name:'指摘が残ったまま、この版を使う',exact:true}).waitFor();
  const markers=await button.getByRole('img',{name:'確認の記録なし',exact:true}).count();
  const observed={runId:id,reviewSeq:review.seq,ref,noCheckMarkers:markers,failedAdoptionLabel:true,browser:browser.version()};
  writeFileSync(`${out}/review-display-${markers?'before':'after'}.json`,JSON.stringify(observed,null,2));
  await page.screenshot({path:`${out}/review-display-${markers?'before':'after'}.png`,fullPage:true});
  assert.equal(markers,0,'An actual review must not be labeled as no check record');
  console.log('PASS live failed review is reflected in both the file tab and adoption label; no adoption performed.');
} finally {await browser.close();}

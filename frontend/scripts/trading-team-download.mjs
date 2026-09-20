// Real UI/API verification only. Run after independent content review passes.
import {chromium} from 'playwright-core';
import {readFileSync, writeFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';

const out=process.env.QUALITY_OUT || '../artifacts/product-quality/trading-team';
const base=process.env.QUALITY_BASE || 'http://127.0.0.1:8802';
const id=readFileSync(`${out}/run-id.txt`,'utf8').trim();
const names=['architecture.md','decisions.md'];
const browser=await chromium.launch({channel:'chrome'});
try {
  const context=await browser.newContext({locale:'ja-JP',viewport:{width:1440,height:1000},acceptDownloads:true});
  const page=await context.newPage(), errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  const getRun=async()=>{const response=await context.request.get(`${base}/api/runs/${id}`);assert.ok(response.ok());return response.json();};
  const before=await getRun();
  assert.equal(before.status,'completed','Incomplete work must not be adopted as verified');
  const targets=names.map(name=>{
    const artifact=before.artifacts.filter(a=>a.logical_path===name).sort((a,b)=>b.revision-a.revision)[0];
    assert.ok(artifact,`Missing ${name}`);
    const task=before.tasks.find(t=>t.spec.id===artifact.task_id);
    assert.ok(task?.review?.results.length,`Missing review for ${name}`);
    assert.ok(task.review.results.every(r=>r.status==='pass'),`Open review findings for ${name}`);
    assert.ok(task.review.target_artifacts.some(a=>a.artifact_id===artifact.artifact_id&&a.revision===artifact.revision&&a.sha256===artifact.sha256),`Review is not bound to ${name}`);
    return artifact;
  });
  await page.goto(`${base}/runs/${id}?view=results`);
  for(const artifact of targets){
    await page.locator('.result-file-list').getByRole('button').filter({hasText:artifact.logical_path}).click();
    await page.getByRole('region',{name:`成果物：${artifact.logical_path}`,exact:true}).waitFor();
    const raw=await context.request.get(`${base}/api/artifacts/${id}/${encodeURIComponent(artifact.artifact_id)}/versions/${artifact.revision}/raw`);
    assert.ok(raw.ok());const bytes=await raw.body();
    assert.equal(createHash('sha256').update(bytes).digest('hex'),artifact.sha256);
    writeFileSync(`${out}/${artifact.logical_path}`,bytes);
    if(await page.locator('[data-adopt]').count()){
      // A failed/unverified button is deliberately not accepted here.
      await page.getByRole('button',{name:'この版を使う',exact:true}).focus();
      await page.keyboard.press('Enter');
    }
    await page.locator('.chosen-pill').waitFor();
  }
  await page.reload();await page.locator('.result-reader').waitFor();
  const after=await getRun();
  for(const a of targets)assert.equal(after.artifact_selection[a.artifact_id]?.revision,a.revision);
  const download=page.waitForEvent('download');
  await page.getByRole('link',{name:'採用したファイルを保存',exact:true}).click();
  await(await download).saveAs(`${out}/selected-browser.zip`);
  for(const width of [1440,390]){
    await page.setViewportSize({width,height:1000});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    await page.screenshot({path:`${out}/selected-${width}.png`,fullPage:true});
  }
  assert.deepEqual(errors,[]);
  writeFileSync(`${out}/selected-run.json`,JSON.stringify(after,null,2));
  writeFileSync(`${out}/download-observation.json`,JSON.stringify({runId:id,browser:browser.version(),targets,adoptionPersisted:true,errors},null,2));
  console.log('PASS reviewed revisions selected via keyboard and persisted; ZIP saved for byte verification.');
} finally {await browser.close();}

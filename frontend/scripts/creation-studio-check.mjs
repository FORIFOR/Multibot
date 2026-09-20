import {chromium} from 'playwright-core'
import AxeBuilder from '@axe-core/playwright'
import assert from 'node:assert/strict'
import {mkdirSync,readFileSync,writeFileSync} from 'node:fs'
const out='../artifacts/product-quality/creation-studio';mkdirSync(out,{recursive:true})
const browser=await chromium.launch({channel:'chrome',headless:true}),context=await browser.newContext({locale:'ja-JP',viewport:{width:1440,height:1100},reducedMotion:'reduce',acceptDownloads:true}),page=await context.newPage()
const evidence={errors:[],writes:[],checks:[],browser:browser.version()};page.on('pageerror',e=>evidence.errors.push(e.message));page.on('request',r=>{if(r.method()!=='GET')evidence.writes.push(r.method()+' '+r.url())})
try{
 const base='http://127.0.0.1:8798',id='run_1a09c8485503d406bf4',run=await(await context.request.get(`${base}/api/runs/${id}`)).json()
 await page.goto(`${base}/runs/${id}?view=results`);await page.getByRole('button',{name:'コピーを編集',exact:true}).waitFor()
 await page.screenshot({path:`${out}/desktop.png`,fullPage:true})
 const rects=await page.evaluate(()=>['room-results','work-conversation'].map(id=>{const r=document.getElementById(id).getBoundingClientRect();return{x:r.x,y:r.y,width:r.width}}));assert.ok(rects[0].x<rects[1].x);assert.ok(rects[0].width>rects[1].width);assert.equal(rects[0].y,rects[1].y)
 await page.getByRole('button',{name:'コピーを編集',exact:true}).click();const editor=page.getByRole('textbox',{name:'成果物のコピーを編集'}),original=await editor.inputValue()
 const actual=run.artifacts.filter(a=>a.artifact_id!=='final-report.md').find(a=>a.revision===Math.max(...run.artifacts.filter(b=>b.artifact_id===a.artifact_id).map(b=>b.revision)))
 const detail=await(await context.request.get(`${base}/api/artifacts/${id}/${actual.artifact_id}/versions/${actual.revision}`)).json();assert.equal(original,detail.text)
 const edited=original+'\n'+readFileSync('../docs/quality/creation-studio.md','utf8').split('\n')[0];await editor.fill(edited)
 const downloadP=page.waitForEvent('download');await page.getByRole('button',{name:'コピーをファイルに保存'}).click();const download=await downloadP;await download.saveAs(`${out}/edited-copy.txt`);assert.equal(readFileSync(`${out}/edited-copy.txt`,'utf8'),edited)
 await page.reload();await page.getByRole('button',{name:'コピーを編集',exact:true}).click();assert.equal(await editor.inputValue(),edited)
 await editor.evaluate(el=>{el.focus();el.setSelectionRange(0,Math.min(35,el.value.length))});await page.getByRole('button',{name:'この版の修正を頼む'}).click();const direction=page.getByRole('textbox',{name:'チームに伝える'});assert.ok((await direction.inputValue()).includes(original.slice(0,35)));assert.ok((await direction.inputValue()).includes(actual.sha256));assert.equal(await direction.evaluate(el=>el===document.activeElement),true)
 await page.getByRole('button',{name:'前の版との差分'}).click();await page.locator('.studio-diff pre').waitFor();const diff=await(await context.request.get(`${base}/api/artifacts/${id}/${actual.artifact_id}/versions/${actual.revision}/diff?from_revision=${actual.revision-1}`)).json();assert.equal(await page.locator('.studio-diff pre').textContent(),diff.diff)
 evidence.checks.push('desktop split','API original match','download bytes match','reload draft recovery','selected excerpt and hash in unsent instruction','exact version diff')
 for(const width of [390,720]){
  await page.setViewportSize({width,height:1100});await page.getByRole('button',{name:/^成果物/}).click();assert.equal(await page.locator('#work-conversation').isVisible(),false);assert.equal(await editor.inputValue(),edited)
  await page.getByRole('button',{name:'会話',exact:true}).click();assert.equal(await page.locator('#room-results').isVisible(),false);assert.ok((await direction.inputValue()).includes(actual.sha256));assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false)
  await page.getByRole('button',{name:/^成果物/}).click();await page.locator('.simple-deliverables').scrollIntoViewIfNeeded();await page.screenshot({path:`${out}/results-${width}.png`});const a=await new AxeBuilder({page}).include('.simple-deliverables').withTags(['wcag2a','wcag2aa']).analyze();assert.deepEqual(a.violations,[])
 }
 await page.getByRole('button',{name:'この版の原文に戻す'}).click();assert.equal(await editor.inputValue(),original)
 const after=await(await context.request.get(`${base}/api/artifacts/${id}/${actual.artifact_id}/versions/${actual.revision}`)).json();assert.equal(after.sha256,actual.sha256);assert.equal(after.text,original)
 evidence.checks.push('390/720 reflow and tab draft retention','axe result area','restore original','server artifact unchanged');assert.deepEqual(evidence.errors,[]);assert.deepEqual(evidence.writes,[]);console.log('PASS',evidence.checks)
}finally{writeFileSync(`${out}/verification.json`,JSON.stringify(evidence,null,2));await browser.close()}

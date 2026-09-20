import {chromium} from 'playwright-core';
import {writeFileSync} from 'node:fs';
import assert from 'node:assert/strict';
const base=process.env.QUALITY_BASE || 'http://127.0.0.1:8802',out=process.env.QUALITY_OUT || '../artifacts/product-quality/trading-team';
const browser=await chromium.launch({channel:'chrome'});
try {
 const ctx=await browser.newContext({locale:'ja-JP',viewport:{width:1440,height:1000}}),p=await ctx.newPage();const errors=[];p.on('pageerror',e=>errors.push(e.message));
 await p.goto(base+'/');
 assert.equal(await p.getByLabel('この依頼に合うチームを自動で組む',{exact:true}).isChecked(),true);
 const goal='株式トレードアプリの実装方法をチームで検討し、architecture.mdとdecisions.mdを作成してください。依頼に必要な専門性と人数を自分で選び、そのチームで設計と検証を完了させてください。全員に係・役の付かない個人名と異なる話し方を与え、send_messageで根拠、異論、質問への回答、成果物の引継ぎを残してください。各人の設定された話し方を使い、架空の会話は作らないでください。添付したtrading-sources.mdを根拠に、Core・証券Adapter・UIの境界、画面、認証認可、注文状態、部分約定、取消競合、応答喪失と再接続、重複防止、価格データ、実装順序、検証条件、未決定事項を具体的に設計してください。Paperだけに限定せず本番接続までの段階を示し、公式仕様・設計提案・未検証を区別してください。実装や実口座接続を実施済みと称さず、外部送信・発注はしないでください。確認役は成果物の実際の版を検査し、誤りがあれば作成担当へ戻してください。';
 await p.locator('#request-goal').fill(goal);await p.locator('details.more').first().locator('summary').click();await p.locator('#run-attachments').setInputFiles('../docs/research/trading-sources.md');await p.locator('.attachment-item').filter({hasText:'trading-sources.md'}).waitFor();
 const responsePromise=p.waitForResponse(r=>r.url()===base+'/api/runs'&&r.request().method()==='POST');await p.getByRole('button',{name:'チームにお願いする',exact:true}).click();const response=await responsePromise;const receipt=await response.json();writeFileSync(`${out}/create-response.json`,JSON.stringify({status:response.status(),body:receipt},null,2));if(receipt.run_id)writeFileSync(`${out}/run-id.txt`,receipt.run_id);assert.ok(response.ok(),JSON.stringify(receipt));await p.waitForURL(/\/runs\//);const id=receipt.run_id;assert.ok(id);
 writeFileSync(`${out}/run-id.txt`,id);let run=await(await ctx.request.get(base+'/api/runs/'+id)).json();for(let tries=0;run.status==='created'&&tries<20;tries++){await p.waitForTimeout(250);run=await(await ctx.request.get(base+'/api/runs/'+id)).json();}writeFileSync(`${out}/initial.json`,JSON.stringify(run,null,2));assert.ok(['planning','running','queued'].includes(run.status));assert.equal(run.inputs.team_selection,'adaptive');assert.deepEqual(errors,[]);
 writeFileSync(`${out}/browser-start.json`,JSON.stringify({runId:id,adaptiveSelected:true,errors,browser:browser.version()},null,2));console.log('STARTED '+id);
}finally{await browser.close()}

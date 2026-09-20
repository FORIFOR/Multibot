import {chromium} from 'playwright-core'
import assert from 'node:assert/strict'
import {mkdirSync,writeFileSync,readFileSync,readdirSync} from 'node:fs'
const out='../artifacts/product-quality/user-journey';mkdirSync(out,{recursive:true})
const b=await chromium.launch({channel:'chrome'}),c=await b.newContext({viewport:{width:1440,height:1000},locale:'ja-JP',reducedMotion:'reduce'}),p=await c.newPage(),base='http://127.0.0.1:8799',id='run_1a09c8485503d406bf4',evidence={checks:[],errors:[]}
p.on('pageerror',e=>evidence.errors.push(e.message))
try{
 const before=await(await c.request.get(`${base}/api/runs/${id}`)).json()
 await p.goto(`${base}/runs/${id}?view=results`);await p.getByRole('button',{name:'コピーを編集',exact:true}).waitFor()
 await p.getByText('版と確認の記録',{exact:true}).click()
 await c.setOffline(true);await p.getByRole('button',{name:'版 1',exact:true}).click();await p.getByRole('alert').filter({hasText:'ファイルを読み込めませんでした'}).waitFor();await c.setOffline(false)
 await p.getByRole('alert').filter({hasText:'ファイルを読み込めませんでした'}).getByRole('button',{name:'再読み込み'}).click();await p.getByRole('button',{name:'コピーを編集',exact:true}).waitFor();assert.equal(await p.getByRole('alert').filter({hasText:'ファイルを読み込めませんでした'}).count(),0);evidence.checks.push('artifact failed fetch then explicit retry without revision change')
 const stoppedDuration=await p.locator('.conversation-elapsed time').getAttribute('datetime')
 const text='readiness.jsonのevidence_quoteをPRODUCTION_PLAN.mdの原文と照合し、引用の翻訳を原文に戻してください。'
 const input=p.getByRole('textbox',{name:'チームに伝える'});await input.fill(text);await c.setOffline(true);await p.getByRole('button',{name:'修正指示を保存',exact:true}).click();await p.getByText('送れませんでした。入力は残してあります。',{exact:true}).waitFor();assert.equal(await input.inputValue(),text);await c.setOffline(false);evidence.checks.push('offline instruction failure retains complete input')
 const baseline=await(await c.request.get(`${base}/api/runs/${id}/events`)).json()
 await p.getByRole('button',{name:'修正指示を保存',exact:true}).dblclick();await p.getByText('指示を保存しました。作業は停止したままです。',{exact:true}).waitFor()
 const after=await(await c.request.get(`${base}/api/runs/${id}`)).json(),events=await(await c.request.get(`${base}/api/runs/${id}/events`)).json();assert.equal(after.status,before.status);assert.equal(await p.locator('.conversation-elapsed time').getAttribute('datetime'),stoppedDuration);assert.equal(after.latest_instruction.payload.text,text);assert.equal(events.filter(e=>e.type==='instruction.received').length-baseline.filter(e=>e.type==='instruction.received').length,1);assert.equal(after.usage.model_calls,before.usage.model_calls)
 await p.reload();await p.getByText('最後に保存した指示を見る',{exact:true}).click();assert.ok((await p.locator('.saved-direction').textContent()).includes(text));await p.screenshot({path:`${out}/saved-instruction.png`});evidence.checks.push('stopped elapsed unchanged after instruction receipt','double click records one instruction','receipt persists after reload','run remains interrupted and model_calls unchanged');await p.getByRole('button',{name:'コピーを編集',exact:true}).click();const editor=p.getByRole('textbox',{name:'成果物のコピーを編集'}),original=await editor.inputValue()
 const documents=readdirSync('../docs/evidence',{recursive:true}).filter(f=>f.endsWith('.jsonl')).map(f=>({name:f,text:readFileSync('../docs/evidence/'+f,'utf8')}))
 const quota=await p.evaluate(docs=>{try{for(const d of docs)localStorage.setItem('journey-evidence:'+d.name,d.text)}catch(e){return e.name}return null},documents);assert.equal(quota,'QuotaExceededError')
 await p.evaluate(lines=>{for(const [i,line]of lines.entries()){try{localStorage.setItem('journey-line:'+i,line)}catch{}}},documents.flatMap(d=>d.text.split('\n')).slice(0,5000))
 await editor.fill(original+'\n'+text);await p.getByText('下書きを保存できません。閉じる前にファイルを保存してください。',{exact:true}).waitFor();const downloadP=p.waitForEvent('download');await p.getByRole('button',{name:'コピーをファイルに保存',exact:true}).click();const d=await downloadP;await d.saveAs(`${out}/quota-recovered.txt`);assert.equal(readFileSync(`${out}/quota-recovered.txt`,'utf8'),original+'\n'+text);evidence.checks.push('real localStorage quota failure disclosed; download recovers edited bytes')
 assert.deepEqual(evidence.errors,[]);console.log('PASS',evidence.checks)
}finally{writeFileSync(`${out}/recovery.json`,JSON.stringify(evidence,null,2));await b.close()}

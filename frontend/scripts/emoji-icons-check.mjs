import {chromium} from 'playwright-core'
import assert from 'node:assert/strict'
import {mkdirSync,writeFileSync} from 'node:fs'
const out='../artifacts/product-quality/emoji-icons';mkdirSync(out,{recursive:true})
const b=await chromium.launch({channel:'chrome',headless:true}),base='http://127.0.0.1:8798'
const c=await b.newContext({locale:'ja-JP',viewport:{width:1440,height:1000}}),p=await c.newPage(),errors=[]
p.on('pageerror',e=>errors.push(e.message))
const cfg=await(await c.request.get(base+'/api/config')).json(),agent=cfg.agents[0];let changed=false
try {
 await p.goto(base+'/settings');const card=p.locator(`#agent-card-${agent.id}`);await card.waitFor()
 await card.getByRole('button',{name:'きつね',exact:true}).click();assert.equal(await card.locator('.bot-custom-emoji').textContent(),'🦊')
 await card.getByRole('button',{name:'変更を保存',exact:true}).click();changed=true;await card.getByRole('status').filter({hasText:'保存しました'}).waitFor()
 let saved=await(await c.request.get(base+'/api/config')).json();assert.equal(saved.agents.find(a=>a.id===agent.id).emoji,'🦊');assert.equal(saved.agents.find(a=>a.id===agent.id).model,agent.model)
 await p.reload();await p.locator(`#agent-card-${agent.id} .bot-custom-emoji`).waitFor();assert.equal(await card.locator('.bot-custom-emoji').textContent(),'🦊')
 for(const width of [1440,390]){await p.setViewportSize({width,height:1000});await card.scrollIntoViewIfNeeded();assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await p.screenshot({path:`${out}/settings-${width}.png`})}
 await p.goto(base+'/');await p.locator('.home-companion .bot-custom-emoji').waitFor();assert.equal(await p.locator('.home-companion .bot-custom-emoji').textContent(),'🦊')
 await p.goto(base+'/runs/run_1a09c8485503d406bf4?view=conversation');await p.locator('.conversation-message .bot-custom-emoji').waitFor();assert.equal(await p.locator('.bot-head').count(),0)
 assert.deepEqual(errors,[]);writeFileSync(`${out}/browser.json`,JSON.stringify({saved:true,reloaded:true,home_reflects:true,historical_chat_emoji:true,errors},null,2));console.log('PASS emoji select/preview/save/reload/home, historical chat, 1440/390')
} finally {
 if(changed){const current=await(await c.request.get(base+'/api/config')).json();const response=await c.request.patch(`${base}/api/agents/${agent.id}`,{data:{expected_revision:current.revision,emoji:agent.emoji||''}});assert.ok(response.ok(),'Restore original isolated icon')}
 await c.close();await b.close()
}

// node --experimental-strip-types --test frontend/tests/request-draft.regression.test.mjs
import assert from 'node:assert/strict';
import { test } from 'node:test';
const key = 'agentteam.requestDraft';
const draft = () => ({ goal: '依頼', text: '資料', urls: '', budget: '1', files: [{name:'notes.md', content:'original'}], selectedAgentIds:['builder'] });
let sequence = 0;
async function setup(saved = null, blocked = false) {
  const data = new Map(saved ? [[key, JSON.stringify(saved)]] : []);
  const storage = { getItem: k => data.get(k) ?? null, setItem(k,v) { if (blocked) throw new Error('quota'); data.set(k,v); }, removeItem: k => data.delete(k) };
  Object.defineProperty(globalThis, 'sessionStorage', { configurable: true, value: storage });
  const module = await import(`../src/lib/request-draft.ts?test=${++sequence}`);
  return { ...module, data, storage };
}
test('valid draft and chosen bot IDs survive reload', async () => {
  const m=await setup(draft()); assert.deepEqual(m.readRequestDraft(), draft());
});
test('invalid optional settings do not discard the request or crash the form', async () => {
  const m=await setup({...draft(), outputPath: {bad:true}, excludedPhrases: 42, selectedAgentIds: 'builder', documentWorkflow:'yes'});
  const read=m.readRequestDraft(); assert.equal(read.goal,'依頼'); assert.equal(read.files[0].content,'original');
  for(const key of ['outputPath','excludedPhrases','selectedAgentIds','documentWorkflow']) assert.equal(read[key], undefined);
});
test('read callers cannot mutate the saved draft by reference', async () => {
  const m=await setup(draft()); const read=m.readRequestDraft(); read.files[0].content='changed'; read.selectedAgentIds.push('other');
  assert.deepEqual(m.readRequestDraft(),draft());
});
test('save callers cannot mutate the memory copy later', async () => {
  const m=await setup(); const value=draft(); assert.equal(m.saveRequestDraft(value),true); value.files[0].content='changed';
  assert.equal(m.readRequestDraft().files[0].content,'original');
});
test('quota failure retains current memory and removes stale stored draft when possible', async () => {
  const m=await setup(draft(),true); const next={...draft(),goal:'new request'};
  assert.equal(m.saveRequestDraft(next),false); assert.equal(m.readRequestDraft().goal,'new request'); assert.equal(m.data.has(key),false);
});
test('explicitly empty team selection is retained', async () => {
  const m=await setup({...draft(),selectedAgentIds:[],adaptiveTeam:false});
  assert.deepEqual(m.readRequestDraft().selectedAgentIds,[]); assert.equal(m.readRequestDraft().adaptiveTeam,false);
});
test('invalid saves do not replace the last valid draft, and clearing removes it', async () => {
  const m=await setup(draft()); m.readRequestDraft(); assert.equal(m.saveRequestDraft({}),false);
  assert.equal(m.readRequestDraft().goal,'依頼'); m.clearRequestDraft(); assert.equal(m.readRequestDraft().goal,''); assert.equal(m.data.has(key),false);
});

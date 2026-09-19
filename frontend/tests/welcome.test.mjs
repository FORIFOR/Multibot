import test from 'node:test'
import assert from 'node:assert/strict'
import { clampStep, markWelcomed, setDraftGoal, takeDraftGoal, welcomed, WELCOME_STEPS } from '../src/lib/welcome.ts'
test('step from the URL is clamped to the real steps', () => { for (const [input, want] of [[0, 0], [1, 1], [2, 2], [3, WELCOME_STEPS - 1], [-4, 0], [1.9, 1], [NaN, 0], [Infinity, 0]]) assert.equal(clampStep(input), want) })
test('when browser storage is blocked the introduction is never forced and nothing throws', () => {
  // Some Node versions ship their own web storage, so simulate a browser that denies access.
  const deny = { get() { throw new Error('denied') }, configurable: true }
  Object.defineProperty(globalThis, 'localStorage', deny); Object.defineProperty(globalThis, 'sessionStorage', deny)
  assert.equal(welcomed(), true); markWelcomed(); setDraftGoal('x'); assert.equal(takeDraftGoal(), '')
  delete globalThis.localStorage; delete globalThis.sessionStorage
})
test('a draft request is handed over once and is bounded', () => {
  const mem = new Map(); const store = { getItem: k => (mem.has(k) ? mem.get(k) : null), setItem: (k, v) => mem.set(k, String(v)), removeItem: k => mem.delete(k) }
  Object.defineProperty(globalThis, 'localStorage', { value: store, configurable: true, writable: true }); Object.defineProperty(globalThis, 'sessionStorage', { value: store, configurable: true, writable: true })
  assert.equal(welcomed(), false); markWelcomed(); assert.equal(welcomed(), true)
  setDraftGoal('a'.repeat(5000)); assert.equal(takeDraftGoal().length, 2000); assert.equal(takeDraftGoal(), '')
  delete globalThis.localStorage; delete globalThis.sessionStorage
})

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { botActivity, botKind, botStateLabel } from '../src/lib/bot-presentation.ts'
import { isBotEmoji, newBotId } from '../src/lib/bot-identity.ts'

for (const status of ['queued', 'ready', 'waiting', 'review_pending']) {
  test(`${status} is not live work`, () => assert.equal(botActivity([{ status }], 'running', 'researcher'), 'waiting'))
}
for (const status of ['cancelled', 'interrupted', 'failed']) {
  test(`${status} stops a stale running task`, () => assert.equal(botActivity([{ status: 'running' }], status, 'builder'), 'stopped'))
}
for (const [id, state] of [['master', 'thinking'], ['researcher', 'researching'], ['builder', 'building'], ['reviewer', 'reviewing'], ['custom-bot', 'building']]) {
  test(`${id} reflects only a running task`, () => assert.equal(botActivity([{ status: 'running' }], 'running', id), state))
}
test('only planner thinks during planning', () => {
  assert.equal(botActivity([], 'planning', 'master'), 'thinking')
  assert.equal(botActivity([], 'planning', 'researcher'), 'idle')
})
test('approval and errors cannot be hidden by active tasks', () => {
  assert.equal(botActivity([{ status: 'running' }, { status: 'approval_required' }], 'running', 'builder'), 'approval')
  assert.equal(botActivity([{ status: 'failed' }, { status: 'running' }], 'running', 'builder'), 'blocked')
})
test('done requires assigned, accepted work', () => {
  assert.equal(botActivity([], 'completed', 'helper'), 'idle')
  assert.equal(botActivity([{ status: 'accepted' }], 'completed', 'builder'), 'done')
  assert.equal(botActivity([{ status: 'running' }], 'completed', 'builder'), 'stopped')
})
test('disabled bot is not animated', () => assert.equal(botActivity([], 'planning', 'master', 'master', false), 'disabled'))
test('role wins over an arbitrary name', () => assert.equal(botKind('review-buddy', 'analyst'), 'helper'))
test('state labels cover both languages', () => {
  assert.equal(botStateLabel('waiting'), '待機中')
  assert.equal(botStateLabel('approval', 'en'), 'Awaiting approval')
})
for (const emoji of ['🦊', '👩🏽‍💻', '🇯🇵', '1️⃣', '👨‍👩‍👧‍👦', '❤️']) {
  test(`complete emoji ${emoji}`, () => assert.equal(isBotEmoji(emoji), true))
}
for (const text of ['', 'fox', '<b>', '🦊🐼', '🦊abc']) {
  test(`reject non-identity ${JSON.stringify(text)}`, () => assert.equal(isBotEmoji(text), false))
}
test('generated IDs are distinct and API-compatible', () => {
  const values = new Set(Array.from({ length: 100 }, newBotId))
  assert.equal(values.size, 100)
  for (const id of values) assert.match(id, /^[a-z][a-z0-9_-]{1,31}$/)
})

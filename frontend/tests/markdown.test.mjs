import test from 'node:test'
import assert from 'node:assert/strict'
import { parseInline, parseMarkdown } from '../src/lib/markdown.ts'
const kinds = text => parseMarkdown(text).map(b => b.t)
const flat = text => JSON.stringify(parseMarkdown(text))
test('headings, lists, tables and code fences become blocks', () => {
  assert.deepEqual(kinds('# 見出し\n\n- **太字** と `code`\n- 二つ目\n\n1. 一\n2. 二\n\n| a | b |\n| --- | --- |\n| 1 | 2 |\n\n```\nuv add x\n```\n\n> 引用\n\n---'), ['h', 'ul', 'ol', 'table', 'pre', 'quote', 'hr'])
  assert.deepEqual(parseInline('**太字** と `code`').map(p => p.t), ['strong', 'text', 'code'])
  assert.equal(parseMarkdown('```\nuv add x\n```')[0].v, 'uv add x')
})
test('there is no HTML block type: raw HTML and scripts stay text', () => {
  const blocks = parseMarkdown('<script>alert(1)</script>\n\n<img src=x onerror=alert(1)>')
  assert.deepEqual(blocks.map(b => b.t), ['p', 'p']); assert.equal(blocks[0].lines[0][0].t, 'text'); assert.equal(blocks[0].lines[0][0].v, '<script>alert(1)</script>')
})
test('only http(s) links become links', () => {
  const parts = parseInline('[docs](https://docs.astral.sh/uv/) と [x](javascript:alert(1)) と https://example.org/a。')
  assert.deepEqual(parts.filter(p => p.t === 'link').map(p => p.href), ['https://docs.astral.sh/uv/', 'https://example.org/a'])
  assert.ok(parts.some(p => p.t === 'text' && p.v.includes('javascript:alert(1)')))
})
test('nothing is dropped, and a one-line summary regains its headings', () => {
  assert.ok(flat('~~取り消し~~ と :::note').includes('~~取り消し~~ と :::note'))
  assert.deepEqual(parseMarkdown('# 最終報告 ## 成果物 - 一件').map(b => [b.t, b.level]), [['h', 1], ['h', 2]])
  const source = '前文\n\n- a\n- b\n\n後文 **x**'; for (const word of ['前文', 'a', 'b', '後文', 'x']) assert.ok(flat(source).includes(word))
})

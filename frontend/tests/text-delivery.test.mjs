import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {textDeliverySchema} from '../src/lib/text-delivery.ts'
const readme=readFileSync(new URL('../../README.md',import.meta.url),'utf8')
const brief=readFileSync(new URL('../../docs/design/brief.md',import.meta.url),'utf8')
test('literal exclusions preserve regex punctuation from actual source text',()=>{
 const phrase=readme.split('\n').find(line=>line.startsWith('**Language.**'))
 assert.ok(phrase)
 const schema=textDeliverySchema(300,600,`${phrase}\n${phrase}\n`)
 assert.equal(schema.not.anyOf.length,1)
 const pattern=new RegExp(schema.not.anyOf[0].pattern)
 assert.ok(pattern.test(readme))
 assert.equal(pattern.test(brief),false)
 assert.equal(schema.minLength,300)
 assert.equal(schema.maxLength,600)
})
test('blank exclusions keep existing text delivery contracts unchanged',()=>{
 assert.deepEqual(textDeliverySchema(undefined,undefined,'\n'),{type:'string'})
})

import test from 'node:test'
import assert from 'node:assert/strict'
import { defaultPanel, isSettled, requestedPanel, resultFiles, statusLabel, stateTone } from '../src/lib/journey.ts'
for (const status of ['created','queued','planning','running','approval_required']) test(`${status} never implies completion`,()=>{assert.equal(defaultPanel(status,5),'team');assert.notEqual(stateTone(status),'good')})
for(const status of ['partial','failed','cancelled','interrupted','blocked']) test(`${status} shows partial results without a success tone`,()=>{assert.equal(defaultPanel(status,1),'results');assert.equal(defaultPanel(status,0),'team');assert.equal(stateTone(status),'attention');assert.ok(isSettled(status));assert.doesNotMatch(statusLabel(status,'ja'),/できたものを見てみよう/)})
test('completed results are discoverable',()=>{assert.equal(defaultPanel('completed',1),'results');assert.equal(stateTone('completed'),'good')})
test('final report alone is not a deliverable',()=>assert.deepEqual(resultFiles([{artifact_id:'final-report.md'},{artifact_id:'report.md'}]),[{artifact_id:'report.md'}]))
test('unknown and malicious view values do not select a panel',()=>{for(const value of ['','?view=garbage','?view=<script>'])assert.equal(requestedPanel(value),null);assert.equal(requestedPanel('?view=results'),'results')})
test('status copy is localized and unknown status is not a success',()=>{assert.match(statusLabel('alien','en'),/Checking/);assert.notEqual(stateTone('alien'),'good');assert.equal(statusLabel('running','ja'),'チームが進めています')})

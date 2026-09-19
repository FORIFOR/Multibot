// Tests of the gate's own logic, NOT tests of any user product or its UI quality.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { run, checkReceipt, sessionPaths } from '../ui-quality.mjs';

const hook = fileURLToPath(new URL('../ui-stop-gate.mjs', import.meta.url));
function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ui-gate-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  fs.mkdirSync(path.join(root, 'src')); fs.mkdirSync(path.join(root, 'artifacts/ui'), { recursive: true });
  fs.writeFileSync(path.join(root, 'src/index.ts'), 'export const x = 1;\n');
  // Tiny valid PNG used only to exercise artifact integrity logic.
  const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aWaYAAAAASUVORK5CYII=', 'base64');
  fs.writeFileSync(path.join(root, 'artifacts/ui/desktop.png'), png);
  const config = { configured: true, inputs: ['src'], checks: [{ name: 'fixture-check', command: [process.execPath, '-e', 'console.log("fixture executed")'] }], requiredImages: ['artifacts/ui/desktop.png'], reviewFile: 'artifacts/ui/review.json', timeoutSeconds: 5, maxReceiptAgeHours: 24 };
  const writeConfig = () => fs.writeFileSync(path.join(root, 'ui-quality.config.json'), JSON.stringify(config));
  writeConfig();
  const review = () => {
    const evidence = run('inspect', undefined, root);
    fs.writeFileSync(path.join(root, config.reviewFile), JSON.stringify({ ...evidence, status: 'pass', reviewer: 'TEST FIXTURE ONLY', blockingFindings: [] }));
  };
  review();
  return { root, config, writeConfig, review };
}
test('matching source, artifacts, checks and review produce a passing local receipt', t => {
  const { root } = fixture(t); run('begin', 's1', root); run('check', 's1', root);
  assert.equal(checkReceipt(root, 's1').status, 'pass');
});
test('source changes invalidate receipt', t => {
  const { root } = fixture(t); run('begin', 's1', root); run('check', 's1', root);
  fs.writeFileSync(path.join(root, 'src/index.ts'), 'export const x = 2;');
  assert.throws(() => checkReceipt(root, 's1'), /Source changed/);
});
test('image changes invalidate receipt', t => {
  const { root } = fixture(t); run('begin', 's1', root); run('check', 's1', root);
  fs.appendFileSync(path.join(root, 'artifacts/ui/desktop.png'), 'changed');
  assert.throws(() => checkReceipt(root, 's1'), /current image/);
});
test('review changes after checks invalidate receipt', t => {
  const { root } = fixture(t); run('begin', 's1', root); run('check', 's1', root);
  fs.appendFileSync(path.join(root, 'artifacts/ui/review.json'), '\n');
  assert.throws(() => checkReceipt(root, 's1'), /Artifact changed/);
});
test('failed command cannot leave a passing receipt', t => {
  const { root, config, writeConfig, review } = fixture(t);
  config.checks[0].command = [process.execPath, '-e', 'process.exit(7)']; writeConfig(); review();
  run('begin', 's1', root); assert.throws(() => run('check', 's1', root), /failed/);
  assert.equal(fs.existsSync(path.join(root, sessionPaths('s1').receipt)), false);
});
test('unconfigured starter is refused', t => {
  const { root, config, writeConfig } = fixture(t); config.configured = false; writeConfig();
  assert.throws(() => run('begin', 's1', root), /configured:true/);
});
test('hook ignores sessions that did not opt in', t => {
  const { root } = fixture(t);
  const result = spawnSync(process.execPath, [hook], { cwd: root, input: JSON.stringify({ cwd: root, session_id: 'other', stop_hook_active: false }), encoding: 'utf8' });
  assert.equal(result.status, 0); assert.equal(result.stdout, '');
});
test('hook blocks once when an active session lacks evidence', t => {
  const { root } = fixture(t); run('begin', 's1', root);
  const result = spawnSync(process.execPath, [hook], { cwd: root, input: JSON.stringify({ cwd: root, session_id: 's1', stop_hook_active: false }), encoding: 'utf8' });
  assert.equal(JSON.parse(result.stdout).decision, 'block');
});
test('retry guard allows an honest blocked handoff without claiming pass', t => {
  const { root } = fixture(t); run('begin', 's1', root);
  const result = spawnSync(process.execPath, [hook], { cwd: root, input: JSON.stringify({ cwd: root, session_id: 's1', stop_hook_active: true }), encoding: 'utf8' });
  assert.equal(result.status, 0); assert.equal(result.stdout, ''); assert.match(result.stderr, /not complete/);
});
test('a different session cannot reuse the receipt', t => {
  const { root } = fixture(t); run('begin', 's1', root); run('check', 's1', root); run('begin', 's2', root);
  assert.throws(() => checkReceipt(root, 's2'));
});
test('expired evidence fails', t => {
  const { root } = fixture(t); run('begin', 's1', root); run('check', 's1', root);
  const p = path.join(root, sessionPaths('s1').receipt); const value = JSON.parse(fs.readFileSync(p));
  value.finishedAt = '2000-01-01T00:00:00.000Z'; fs.writeFileSync(p, JSON.stringify(value));
  assert.throws(() => checkReceipt(root, 's1'), /expired/);
});
test('missing source inputs fail rather than silently passing', t => {
  const { root, config, writeConfig } = fixture(t); config.inputs = ['missing-source']; writeConfig();
  assert.throws(() => run('inspect', undefined, root), /None of the configured/);
});
test('a blocked review never passes', t => {
  const { root, config } = fixture(t); const p = path.join(root, config.reviewFile);
  const value = JSON.parse(fs.readFileSync(p)); value.status = 'blocked'; fs.writeFileSync(p, JSON.stringify(value));
  run('begin', 's1', root); assert.throws(() => run('check', 's1', root), /has not passed/);
});
test('a source symlink cannot escape the project scope', t => {
  const { root } = fixture(t); fs.symlinkSync(os.tmpdir(), path.join(root, 'src/external'));
  assert.throws(() => run('inspect', undefined, root), /Symlink/);
});

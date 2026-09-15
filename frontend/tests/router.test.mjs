// Isolated tests of the real router module with hooks/JSX mocked, not React DOM.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';

const source = fs.readFileSync(new URL('../src/lib/router.tsx', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { reportDiagnostics: true, compilerOptions: {
  module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.React,
}});
assert.equal(compiled.diagnostics.filter(d => d.category === ts.DiagnosticCategory.Error).length, 0);

function harness(initial = '/runs/one?tab=approvals') {
  const listeners = new Map();
  let state;
  let cleanup;
  const win = {
    location: new URL(initial, 'https://local.example'),
    history: { pushState(_state, _unused, path) { win.location = new URL(path, win.location); } },
    addEventListener(name, fn) { listeners.set(name, fn); },
    removeEventListener(name, fn) { if (listeners.get(name) === fn) listeners.delete(name); },
  };
  const react = {
    useState(initialValue) { if (state === undefined) state = initialValue; return [state, value => { state = value; }]; },
    useEffect(effect) { cleanup = effect(); },
    createElement(type, props, ...children) { return { type, props, children }; },
  };
  const context = { exports: {}, window: win, React: react, require(name) {
    assert.equal(name, 'react'); return react;
  } };
  vm.runInNewContext(compiled.outputText, context);
  return { router: context.exports, win, listeners, state: () => state, cleanup: () => cleanup?.() };
}

for (const [path, id] of [
  ['/runs/one', 'one'], ['/runs/one?tab=approvals', 'one'],
  ['/runs/one#report', 'one'], ['/runs/one?tab=approvals#details', 'one'],
  ['/runs/', null], ['/settings?run=one', null],
]) test(`run identifier: ${path}`, () => {
  assert.equal(harness().router.getRunId(path), id);
});

test('initial, push and history navigation preserve query and fragment consistently', () => {
  const h = harness('/runs/one?tab=chat#first');
  const [initial, nav] = h.router.usePath();
  assert.equal(initial, '/runs/one?tab=chat#first');
  nav('/runs/one?tab=approvals');
  assert.equal(h.state(), '/runs/one?tab=approvals');
  h.win.location = new URL('https://local.example/runs/one?tab=chat#first');
  h.listeners.get('popstate')();
  assert.equal(h.state(), '/runs/one?tab=chat#first');
  h.cleanup();
  assert.equal(h.listeners.size, 0);
});

test('only an unmodified primary click is intercepted', () => {
  const h = harness();
  const calls = [];
  const link = h.router.Link({ to: '/runs/one?tab=approvals', nav: path => calls.push(path), children: 'Review' });
  for (const modifiers of [{metaKey: true}, {ctrlKey: true}, {shiftKey: true}, {altKey: true}, {button: 1}, {defaultPrevented: true}]) {
    let prevented = false;
    link.props.onClick({ button: 0, ...modifiers, preventDefault() { prevented = true; } });
    assert.equal(prevented, false);
  }
  assert.equal(calls.length, 0);
  let prevented = false;
  link.props.onClick({ button: 0, preventDefault() { prevented = true; } });
  assert.equal(prevented, true);
  assert.deepEqual(calls, ['/runs/one?tab=approvals']);
});

test('workspace uses a clean run ID and resets run-local state on route changes', () => {
  const app = fs.readFileSync(new URL('../src/App.tsx', import.meta.url), 'utf8');
  assert.match(app, /const runId = getRunId\(path\)/);
  assert.match(app, /<RunView key=\{path\} runId=\{runId\}/);
});

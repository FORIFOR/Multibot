#!/usr/bin/env node
/** Local evidence consistency gate. Not an aesthetic evaluator or tamper-proof CI gate. */
import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const CONFIG = 'ui-quality.config.json';
const EXCLUDED = new Set(['node_modules', '.git', '.next', 'dist', 'build', 'target', '.ui-quality', 'artifacts', 'test-results', 'playwright-report']);
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
export function projectRoot(cwd = process.cwd()) {
  const result = spawnSync('git', ['rev-parse', '--show-toplevel'], { cwd, encoding: 'utf8', timeout: 5000 });
  return path.resolve(result.status === 0 ? result.stdout.trim() : cwd);
}
function localPath(root, relative) {
  if (typeof relative !== 'string' || !relative || path.isAbsolute(relative)) throw new Error(`Expected a relative project path: ${relative}`);
  const absolute = path.resolve(root, relative);
  if (absolute === root || !absolute.startsWith(root + path.sep)) throw new Error(`Path outside project or project root not allowed: ${relative}`);
  // Reject symlinks to avoid reading/writing outside the scoped project.
  let current = root;
  for (const piece of path.relative(root, absolute).split(path.sep)) {
    current = path.join(current, piece);
    if (fs.existsSync(current) && fs.lstatSync(current).isSymbolicLink()) throw new Error(`Symlink needs an explicit in-project path: ${relative}`);
  }
  return absolute;
}
function readJSON(root, relative) { return JSON.parse(fs.readFileSync(localPath(root, relative), 'utf8')); }
function writeJSON(root, relative, data) {
  const target = localPath(root, relative);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, JSON.stringify(data, null, 2) + '\n');
}
export function loadConfig(root) {
  const config = readJSON(root, CONFIG);
  if (config.configured !== true) throw new Error('Adapt ui-quality.config.json to the real project and explicitly set configured:true.');
  if (!Array.isArray(config.inputs) || config.inputs.length === 0) throw new Error('inputs must enumerate actual source/config/test paths.');
  if (!Array.isArray(config.checks) || config.checks.length === 0) throw new Error('At least one real check is required.');
  const names = new Set();
  for (const check of config.checks) {
    if (!check.name || names.has(check.name) || !Array.isArray(check.command) || !check.command.length || check.command.some(s => typeof s !== 'string' || !s)) throw new Error('Each check needs a unique name and a non-empty argv array.');
    names.add(check.name);
  }
  if (!Array.isArray(config.requiredImages) || !config.requiredImages.length) throw new Error('At least one required image is necessary.');
  if (!Number.isFinite(config.timeoutSeconds) || config.timeoutSeconds <= 0 || config.timeoutSeconds > 3600) throw new Error('timeoutSeconds must be in (0,3600].');
  if (!Number.isFinite(config.maxReceiptAgeHours) || config.maxReceiptAgeHours <= 0) throw new Error('maxReceiptAgeHours must be positive.');
  [...config.inputs, ...config.requiredImages, config.reviewFile].forEach(p => localPath(root, p));
  return config;
}
export function fingerprint(root, config) {
  const files = new Set([CONFIG]);
  let existingInputs = 0;
  function walk(relative) {
    const absolute = localPath(root, relative);
    if (!fs.existsSync(absolute)) return;
    const stat = fs.lstatSync(absolute);
    if (stat.isDirectory()) {
      for (const name of fs.readdirSync(absolute).sort()) {
        if (!EXCLUDED.has(name)) walk(path.join(relative, name));
      }
    } else if (stat.isFile()) files.add(relative);
  }
  for (const input of config.inputs) {
    if (fs.existsSync(localPath(root, input))) existingInputs++;
    walk(input);
  }
  if (!existingInputs) throw new Error('None of the configured input paths exist.');
  const digest = createHash('sha256');
  for (const relative of [...files].sort()) {
    digest.update(relative.replaceAll(path.sep, '/') + '\0');
    digest.update(sha(fs.readFileSync(localPath(root, relative))) + '\0');
  }
  return digest.digest('hex');
}
function imageRecords(root, config) {
  return config.requiredImages.map(relative => {
    const bytes = fs.readFileSync(localPath(root, relative));
    // This starter captures PNGs; checking the signature avoids accepting empty placeholders.
    if (bytes.length < 32 || bytes.subarray(0, 8).toString('hex') !== '89504e470d0a1a0a') throw new Error(`Missing/invalid PNG: ${relative}`);
    return { path: relative, sha256: sha(bytes) };
  });
}
function reviewRecord(root, config, sourceFingerprint, images) {
  const review = readJSON(root, config.reviewFile);
  if (review.status !== 'pass' || !Array.isArray(review.blockingFindings) || review.blockingFindings.length) throw new Error('Independent review has not passed or has blocking findings.');
  if (typeof review.reviewer !== 'string' || !review.reviewer.trim()) throw new Error('Review must name its reviewer.');
  if (review.sourceFingerprint !== sourceFingerprint) throw new Error('Review belongs to different source content. Re-review current images.');
  for (const image of images) {
    if (!review.images?.some(item => item.path === image.path && item.sha256 === image.sha256)) throw new Error(`Review does not match current image: ${image.path}`);
  }
  return { path: config.reviewFile, sha256: sha(fs.readFileSync(localPath(root, config.reviewFile))) };
}
export function sessionPaths(session) {
  if (typeof session !== 'string' || !session.trim() || session.includes('${')) throw new Error('A real Claude session ID or a deliberate local session name is required.');
  const id = sha(session);
  return { active: `.ui-quality/sessions/${id}/active.json`, receipt: `.ui-quality/sessions/${id}/receipt.json`, logDir: `.ui-quality/sessions/${id}/logs` };
}
export function checkReceipt(root, session) {
  const config = loadConfig(root);
  const files = sessionPaths(session);
  const active = readJSON(root, files.active);
  const receipt = readJSON(root, files.receipt);
  if (active.session !== session || receipt.session !== session || receipt.status !== 'pass') throw new Error('Session receipt mismatch.');
  const age = Date.now() - Date.parse(receipt.finishedAt);
  if (!Number.isFinite(age) || age < -60000 || age > config.maxReceiptAgeHours * 3600000) throw new Error('Evidence receipt is expired or has an invalid date.');
  const sourceFingerprint = fingerprint(root, config);
  if (receipt.sourceFingerprint !== sourceFingerprint) throw new Error('Source changed after checks. Repeat capture, review and checks.');
  const images = imageRecords(root, config);
  const review = reviewRecord(root, config, sourceFingerprint, images);
  for (const artifact of [...images, review]) {
    if (!receipt.artifacts?.some(item => item.path === artifact.path && item.sha256 === artifact.sha256)) throw new Error(`Artifact changed after checks: ${artifact.path}`);
  }
  if (receipt.checks?.length !== config.checks.length) throw new Error('Missing check results.');
  for (const check of config.checks) {
    if (!receipt.checks.some(result => result.name === check.name && result.exitCode === 0)) throw new Error(`Missing passing result: ${check.name}`);
  }
  return receipt;
}
export function run(command, session, root = projectRoot()) {
  if (command === 'end') {
    fs.rmSync(localPath(root, sessionPaths(session).active), { force: true });
    return { status: 'ended', note: 'Gate deactivated; this does not mark UI complete.' };
  }
  const config = loadConfig(root);
  if (command === 'inspect') return { sourceFingerprint: fingerprint(root, config), images: imageRecords(root, config) };
  const files = sessionPaths(session);
  if (command === 'begin') {
    writeJSON(root, files.active, { session, startedAt: new Date().toISOString() });
    fs.rmSync(localPath(root, files.receipt), { force: true });
    return { status: 'active', session };
  }
  if (command === 'assert') return checkReceipt(root, session);
  if (command !== 'check') throw new Error('Usage: ui-quality.mjs begin|check|assert|end <session>, or inspect');
  readJSON(root, files.active); // Explicit opt-in is required.
  fs.rmSync(localPath(root, files.receipt), { force: true });
  const sourceFingerprint = fingerprint(root, config);
  const startedAt = new Date().toISOString();
  const checks = [];
  fs.mkdirSync(localPath(root, files.logDir), { recursive: true });
  for (const [index, check] of config.checks.entries()) {
    console.error(`[ui-quality] Running ${check.name}`);
    const result = spawnSync(check.command[0], check.command.slice(1), {
      cwd: root, shell: false, encoding: 'utf8', timeout: config.timeoutSeconds * 1000,
      maxBuffer: 16 * 1024 * 1024,
    });
    const logFile = `${files.logDir}/${index}.log`;
    fs.writeFileSync(localPath(root, logFile), (result.stdout ?? '') + (result.stderr ?? '') + (result.error ? `\n${result.error.message}\n` : ''));
    if (result.error || result.status !== 0) throw new Error(`${check.name} failed (exit ${result.status ?? 'none'}). See ${logFile}. No passing receipt was written.`);
    checks.push({ name: check.name, exitCode: 0, logFile });
  }
  if (fingerprint(root, config) !== sourceFingerprint) throw new Error('Source was modified while checks ran. Repeat with stable source content.');
  const images = imageRecords(root, config);
  const review = reviewRecord(root, config, sourceFingerprint, images);
  const receipt = { kind: 'local-evidence-consistency', status: 'pass', session, sourceFingerprint, startedAt, finishedAt: new Date().toISOString(), checks, artifacts: [...images, review] };
  writeJSON(root, files.receipt, receipt);
  return receipt;
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try { console.log(JSON.stringify(run(process.argv[2], process.argv[3]), null, 2)); }
  catch (error) { console.error(`[ui-quality] ${error.message}`); process.exitCode = 1; }
}

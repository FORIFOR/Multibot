#!/usr/bin/env node
/** Optional cheap Stop hook. Only acts for sessions explicitly activated with 'begin'. */
import fs from 'node:fs';
import path from 'node:path';
import { checkReceipt, projectRoot, sessionPaths } from './ui-quality.mjs';

try {
  const input = JSON.parse(fs.readFileSync(0, 'utf8'));
  const root = projectRoot(input.cwd ?? process.cwd());
  const activePath = path.join(root, sessionPaths(input.session_id).active);
  if (fs.existsSync(activePath)) {
    if (input.stop_hook_active) {
      // Permit honest partial handoff; do not trap the agent in an unbounded retry loop.
      console.error('[ui-quality] Retry guard: stopping is allowed, but unmet checks remain unmet. Report BLOCKED/UNVERIFIED, not complete.');
    } else {
      try { checkReceipt(root, input.session_id); }
      catch (error) {
        console.log(JSON.stringify({
          decision: 'block',
          reason: `UI evidence is missing or stale: ${error.message} Run the configured checks and inspect current screenshots. If the environment prevents verification, report the exact blocker and UNVERIFIED scope; do not fabricate PASS.`,
        }));
      }
    }
  }
} catch (error) {
  console.error(`[ui-quality] Hook could not evaluate evidence: ${error.message}. This is not a PASS.`);
  process.exitCode = 1;
}

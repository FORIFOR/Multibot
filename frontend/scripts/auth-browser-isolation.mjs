/** Real browser + real secured HTTP/SQLite. No provider calls, mocked responses, or invented documents.
 * Required: AUTH_TEST_URL, AUTH_TEST_ADMIN_KEY_FILE, AUTH_TEST_OPERATOR_KEY_FILE,
 * AUTH_TEST_DATA_DIR, AUTH_TEST_EVIDENCE_DIR. Use a dedicated verification installation only.
 * The expiry check revokes browser sessions in that installation's SQLite.
 */
import { chromium } from 'playwright-core'
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'
import assert from 'node:assert/strict'

const origin = process.env.AUTH_TEST_URL
const adminFile = process.env.AUTH_TEST_ADMIN_KEY_FILE
const operatorFile = process.env.AUTH_TEST_OPERATOR_KEY_FILE
const dataDir = process.env.AUTH_TEST_DATA_DIR
const out = process.env.AUTH_TEST_EVIDENCE_DIR
assert.ok(origin && adminFile && operatorFile && dataDir && out, 'Provide explicit isolated server, credential-file, SQLite and evidence paths.')
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(origin).hostname), 'Run only against an isolated loopback installation.')
const repo = fileURLToPath(new URL('../../', import.meta.url))
const sourcePath = resolve(repo, 'docs/PRODUCTION_PLAN.md')
const source = readFileSync(sourcePath, 'utf8')
const recordedArtifact = JSON.parse(readFileSync(resolve(repo, 'docs/evidence/real-readiness-v61-qwen35-fixed-20260925/01-run_1a0d74b88812173eb2c-artifacts.json'), 'utf8'))[0]
const recordedCopy = readFileSync(resolve(repo, 'docs/evidence/real-readiness-v61-qwen35-fixed-20260925/01-run_1a0d74b88812173eb2c-draft-r1.json'), 'utf8')
const artifactKey = `artifact-draft:${recordedArtifact.run_id}:${recordedArtifact.artifact_id}:${recordedArtifact.revision}:${recordedArtifact.sha256}`
const goal = source.split('\n').find(line => line.startsWith('Goal:'))
assert.ok(goal, 'Use the actual production-plan goal, not substitute test content.')
const sha256 = value => createHash('sha256').update(value).digest('hex')
const initialRuns = JSON.parse(execFileSync('sqlite3', ['-json', resolve(dataDir, 'agentteam.sqlite'), 'SELECT count(*) AS runs FROM runs;'], { encoding: 'utf8' }))[0].runs
const checks = []
const record = (id, observed) => checks.push({ id, method: 'Chrome with real secured API and SQLite', expected: observed, observed, status: 'PASS' })
mkdirSync(out, { recursive: true })
const browser = await chromium.launch({ channel: 'chrome' })
const context = await browser.newContext({ locale: 'ja-JP', viewport: { width: 1280, height: 900 } })
const page = await context.newPage()
page.setDefaultTimeout(12000)
const login = async (target, keyFile) => {
  await target.locator('#access-key').fill(readFileSync(keyFile, 'utf8').trim())
  await target.getByRole('button', { name: 'ログイン', exact: true }).click()
  await target.locator('.side-new').waitFor()
  await target.locator('.side-new').click()
  await target.locator('#request-goal').waitFor()
}
const seedDraft = async target => {
  await target.locator('#request-goal').fill(goal)
  await target.locator('details').evaluateAll(nodes => nodes.forEach(node => { node.open = true }))
  await target.locator('#run-attachments').setInputFiles(sourcePath)
  await target.waitForFunction(() => JSON.parse(sessionStorage.getItem('agentteam.requestDraft') || 'null')?.files?.length === 1)
}
const state = target => target.evaluate(() => ({
  request: sessionStorage.getItem('agentteam.requestDraft'),
  welcome: sessionStorage.getItem('agentteam.draftGoal'),
  search: sessionStorage.getItem('work-list-search'),
  copies: Object.keys(localStorage).filter(key => key.startsWith('artifact-draft:')),
}))
const clean = s => {
  const draft = JSON.parse(s.request || 'null')
  return (!draft || (draft.goal === '' && draft.text === '' && draft.files.length === 0)) && !s.welcome && !s.search && s.copies.length === 0
}
try {
  await page.goto(origin)
  await login(page, adminFile)
  await seedDraft(page)
  await page.reload()
  await page.locator('#request-goal').waitFor()
  assert.equal(await page.locator('#request-goal').inputValue(), goal)
  assert.equal(JSON.parse((await state(page)).request).files[0].content, source)
  record('same-principal-reload', '依頼と実資料添付を同一主体の再読込で保持')

  // These are the real application storage paths; values are repository source text.
  // Artifact editor cleanup is checked at its storage boundary, not claimed as editor UI coverage.
  await page.evaluate(({ text, artifactKey, recordedCopy }) => {
    sessionStorage.setItem('agentteam.draftGoal', text)
    sessionStorage.setItem('work-list-search', text)
    localStorage.setItem(artifactKey, recordedCopy)
  }, { text: source, artifactKey, recordedCopy })
  await page.getByRole('button', { name: 'ログアウト', exact: true }).click()
  await page.locator('#access-key').waitFor()
  assert.ok(clean(await state(page)))
  assert.equal(await page.evaluate(async () => (await fetch('/api/auth/me')).status), 401)
  record('signout-clears-private-data', 'サーバーセッション失効と依頼・添付・welcome入力・検索・編集コピーの消去')
  await login(page, operatorFile)
  assert.equal(await page.locator('#request-goal').inputValue(), '')
  assert.ok(clean(await state(page)))
  record('next-principal-is-empty', '別主体へ前利用者の内容を表示しない')

  await seedDraft(page)
  const second = await context.newPage()
  await second.goto(origin)
  await second.locator('#request-goal').waitFor()
  await seedDraft(second)
  await second.getByRole('button', { name: 'ログアウト', exact: true }).click()
  await second.locator('#access-key').waitFor()
  await page.locator('#access-key').waitFor()
  assert.ok(clean(await state(page)))
  record('other-tab-signout', '他タブのログアウトで既存画面を閉じ、タブ内の依頼と添付を消去')
  await login(second, adminFile)
  await page.locator('#access-key').waitFor()
  assert.equal(await page.locator('#request-goal').count(), 0)
  assert.ok(clean(await state(page)))
  record('other-tab-signin', '他タブが別主体でログインしても旧主体の画面・下書きを復元しない')
  await second.close()

  await page.reload()
  await page.locator('#request-goal').waitFor()
  await seedDraft(page)
  execFileSync('sqlite3', [resolve(dataDir, 'agentteam.sqlite'), 'DELETE FROM auth_sessions;'])
  await page.getByRole('link', { name: '作業一覧', exact: true }).click()
  await page.locator('#access-key').waitFor()
  assert.ok(clean(await state(page)))
  await login(page, operatorFile)
  assert.equal(await page.locator('#request-goal').inputValue(), '')
  record('server-revocation-401', '実SQLiteのセッション失効後のHTTP 401でメモリも消去し、同一ページの再ログインで漏れない')
  const counts = JSON.parse(execFileSync('sqlite3', ['-json', resolve(dataDir, 'agentteam.sqlite'), 'SELECT count(*) AS runs FROM runs;'], { encoding: 'utf8' }))[0]
  assert.equal(counts.runs, initialRuns, 'Verification must not submit work or call a model.')
  record('no-model-execution', '追加run記録0件。依頼送信・LLM呼出しなし')
  await page.screenshot({ path: resolve(out, 'next-principal-empty.png'), fullPage: true })
  writeFileSync(resolve(out, 'results.json'), JSON.stringify({ checked_at: new Date().toISOString(), browser: browser.version(), source: 'docs/PRODUCTION_PLAN.md', source_sha256: sha256(source), checks, limitations: ['同一OS/ブラウザプロファイルの悪意ある手動ストレージ操作の隔離ではない', '編集コピーは保存境界の消去確認。成果物エディタの操作試験ではない', '実IdP/公開TLS/実ユーザー受入・LLM業務品質の検証ではない'] }, null, 2) + '\n')
  console.log(JSON.stringify({ passed: checks.length, evidence: resolve(out, 'results.json') }))
} catch (error) {
  writeFileSync(resolve(out, 'failure.json'), JSON.stringify({ checks, error: String(error), visible_text: await page.locator('body').innerText() }, null, 2) + '\n')
  await page.screenshot({ path: resolve(out, 'failure.png'), fullPage: true })
  throw error
} finally { await browser.close() }

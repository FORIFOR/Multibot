// GitHub-only real Keycloak/code-flow/API regression. Never fabricates a JWT,
// substitutes a network response, changes a clock, or starts model execution.
import { chromium } from 'playwright-core'
import { createServer } from 'node:http'
import { randomBytes, createHash } from 'node:crypto'
import { readFileSync, writeFileSync } from 'node:fs'
import { execFile } from 'node:child_process'
import { promisify } from 'node:util'

if (process.env.GITHUB_ACTIONS !== 'true') throw new Error('Disposable GitHub runner required')
const root = process.env.OIDC_ROOT
if (!root || process.env.OIDC_CONTAINER !== 'multibot-public-oidc') throw new Error('Dedicated OIDC root/container required')
process.umask(0o077)
const run = promisify(execFile)
const read = name => readFileSync(`${root}/${name}`, 'utf8')
const save = (name, value) => writeFileSync(`${root}/${name}`, typeof value === 'string' ? value : JSON.stringify(value, null, 2) + '\n', { mode: 0o600 })
const provenance = JSON.parse(read('provenance.json'))
const { origin, issuer, client_id: clientId } = provenance
const passwords = JSON.parse(read('staging-users.json'))
const clientSecret = read('client-secret')
const emergencyKey = read('emergency-admin.key').trim()
const callbackUri = 'http://127.0.0.1:8802/callback'
const report = { ...provenance, started_at: new Date().toISOString(), status: 'RUNNING', checks: [], http: [], jwks_observations: [] }
const secrets = [clientSecret, emergencyKey, ...Object.values(passwords)]
let stage = 'setup', browser, callback, pending, paused = false
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms))
function ensure(value, id) { if (!value) throw new Error(id) }
function pass(id) { report.checks.push(id); save('report.json', report) }
async function withinDeadline(action, milliseconds) {
  let timer
  try {
    return await Promise.race([Promise.resolve().then(action), new Promise((_, reject) => {
      timer = setTimeout(() => reject(new Error('cleanup_deadline_exceeded')), milliseconds)
    })])
  } finally { clearTimeout(timer) }
}
function privateFailure(name, error) {
  try { save(name, String(error.stack || error)) }
  catch { report.private_log_write_failed = true }
}
async function fetchBounded(url, options = {}) {
  return fetch(url, { ...options, signal: AbortSignal.timeout(15000), redirect: 'error' })
}
async function api(path, token, expected, options = {}) {
  const response = await fetchBounded(origin + path, { ...options, headers: { Authorization: `Bearer ${token}`, ...options.headers } })
  report.http.push({ stage, path, method: options.method || 'GET', status: response.status, expected })
  ensure(response.status === expected, 'unexpected_api_status')
  return response
}
async function docker(...args) {
  return run('docker', [...args, process.env.OIDC_CONTAINER], { timeout: 20000, maxBuffer: 4 * 1024 * 1024 })
}
async function certCount(label) {
  // Keycloak logs only method, URL PATH and status. Never print the raw logs.
  await sleep(300)
  const logs = await docker('logs')
  save('keycloak.private.log', logs.stdout + logs.stderr)
  const path = '/realms/agentteam-verification/protocol/openid-connect/certs'
  const count = (logs.stdout + logs.stderr).split('\n').filter(line => line.endsWith(`OIDC-JWKS-ACCESS GET ${path} 200`)).length
  report.jwks_observations.push({ label, successful_certs_gets: count })
  return count
}
async function pauseIdp() { await docker('pause'); paused = true }
async function unpauseIdp() { await docker('unpause'); paused = false }
function tokenPart(token, index) { return JSON.parse(Buffer.from(token.split('.')[index], 'base64url').toString()) }

async function realTokens(name) {
  const context = await browser.newContext()
  const page = await context.newPage()
  const verifier = randomBytes(32).toString('base64url')
  const state = randomBytes(24).toString('base64url')
  const nonce = randomBytes(24).toString('base64url')
  let timer
  const result = new Promise((resolve, reject) => { pending = { verifier, state, resolve, reject } })
  result.catch(() => {}) // The callback can reject while Playwright is still completing the click.
  try {
    const url = new URL(issuer + '/protocol/openid-connect/auth')
    url.search = new URLSearchParams({ client_id: clientId, redirect_uri: callbackUri, response_type: 'code',
      scope: 'openid profile', state, nonce, code_challenge_method: 'S256',
      code_challenge: createHash('sha256').update(verifier).digest('base64url') }).toString()
    await page.goto(url.toString())
    await page.locator('#username').fill(name)
    await page.locator('#password').fill(passwords[name])
    await page.locator('#kc-login').click()
    const issued = await Promise.race([result, new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('code_flow_timeout')), 30000) })])
    for (const key of ['access_token', 'id_token', 'refresh_token']) if (issued[key]) secrets.push(issued[key])
    // This is a correlation check, not independent ID-token validation. The
    // application independently verifies each access token against real JWKS.
    ensure(tokenPart(issued.id_token, 1).nonce === nonce, 'nonce_correlation')
    const claims = tokenPart(issued.access_token, 1)
    const header = tokenPart(issued.access_token, 0)
    const required = ['exp', 'iat', 'iss', 'aud', 'sub', 'azp']
    report.token_preconditions ||= []
    report.token_preconditions.push({ account: name,
      unverified_metadata_only: true,
      required_claims_present: Object.fromEntries(required.map(key => [key, claims[key] !== undefined && claims[key] !== null])),
      rs256: header.alg === 'RS256', kid_present: typeof header.kid === 'string',
      issuer_matches: claims.iss === issuer, client_matches: claims.azp === clientId,
      audience_matches: [claims.aud].flat().includes('agentteam-api'),
      group_array_present: Array.isArray(claims.groups), lifetime_seconds: claims.exp - claims.iat })
    ensure(required.every(key => claims[key] !== undefined && claims[key] !== null), 'issued_access_token_missing_required_claim')
    return issued
  } finally {
    clearTimeout(timer); pending = null
    await withinDeadline(() => context.close(), 10000)
  }
}

try {
  save('report.json', report)
  stage = 'real_keycloak_setup'
  const bootstrap = Object.fromEntries(read('keycloak.env').trim().split('\n').map(line => {
    const index = line.indexOf('='); return [line.slice(0, index), line.slice(index + 1)]
  }))
  secrets.push(bootstrap.KC_BOOTSTRAP_ADMIN_PASSWORD)
  let idpAdmin
  async function bootstrapToken() {
    if (idpAdmin && tokenPart(idpAdmin, 1).exp * 1000 > Date.now() + 10000) return
    const response = await fetchBounded('http://127.0.0.1:8801/realms/master/protocol/openid-connect/token', {
      method: 'POST', body: new URLSearchParams({ grant_type: 'password', client_id: 'admin-cli',
        username: bootstrap.KC_BOOTSTRAP_ADMIN_USERNAME, password: bootstrap.KC_BOOTSTRAP_ADMIN_PASSWORD }) })
    ensure(response.status === 200, 'bootstrap_authentication')
    const issued = await response.json()
    idpAdmin = issued.access_token
    for (const key of ['access_token', 'id_token', 'refresh_token']) if (issued[key]) secrets.push(issued[key])
  }
  async function administer(path, method = 'GET', body, expected = 200) {
    await bootstrapToken()
    const response = await fetchBounded('http://127.0.0.1:8801/admin/realms/agentteam-verification' + path, {
      method, headers: { Authorization: `Bearer ${idpAdmin}`, 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body) })
    ensure(response.status === expected, 'keycloak_administration_status')
    return response
  }
  // Do not invent an email or personal name to satisfy default profile rules.
  const profile = await (await administer('/users/profile')).json()
  for (const attribute of profile.attributes) if (['email', 'firstName', 'lastName'].includes(attribute.name)) delete attribute.required
  const savedProfile = await (await administer('/users/profile', 'PUT', profile)).json()
  const optional = savedProfile.attributes.filter(a => ['email', 'firstName', 'lastName'].includes(a.name))
  ensure(optional.length === 3 && optional.every(a => !a.required), 'optional_personal_attributes')
  const users = await (await administer('/users')).json()
  ensure(users.length === Object.keys(passwords).length && users.every(u => passwords[u.username] && !u.email && !u.firstName && !u.lastName), 'technical_accounts_without_personal_data')
  pass('real_technical_accounts_without_fabricated_person_or_email')
  callback = createServer(async (req, res) => {
    const url = new URL(req.url, callbackUri)
    if (url.pathname !== '/callback' || !pending || url.searchParams.get('state') !== pending.state) { res.writeHead(400).end(); return }
    const operation = pending; pending = null
    try {
      const code = url.searchParams.get('code')
      ensure(Boolean(code), 'authorization_code_missing'); secrets.push(code)
      const response = await fetchBounded(issuer + '/protocol/openid-connect/token', { method: 'POST', body: new URLSearchParams({
        grant_type: 'authorization_code', client_id: clientId, client_secret: clientSecret,
        redirect_uri: callbackUri, code, code_verifier: operation.verifier }) })
      ensure(response.status === 200, 'authorization_code_exchange')
      const issued = await response.json()
      res.writeHead(200, { 'Content-Type': 'text/plain', 'Cache-Control': 'no-store' }).end('Authorization received.')
      operation.resolve(issued)
    } catch { res.writeHead(502).end(); operation.reject(new Error('authorization_code_exchange')) }
  })
  await new Promise((resolve, reject) => { callback.once('error', reject); callback.listen(8802, '127.0.0.1', resolve) })
  browser = await chromium.launch({ channel: 'chrome', headless: true })
  report.chrome_version = browser.version()
  const admin = await realTokens('verification-admin')
  stage = 'initial_jwks_fetch'
  ensure(await certCount('before_first_api_token') === 0, 'unexpected_prior_jwks_fetch')
  const firstApiStarted = performance.now()
  report.jwks_timing = { cache_ttl_seconds: 60, first_api_started_at: new Date().toISOString() }
  const first = await (await api('/api/auth/me', admin.access_token, 200)).json()
  ensure(first.role === 'admin' && first.source === 'oidc', 'verified_admin_identity')
  ensure(await certCount('first_valid_token') === 1, 'initial_fetch_count')
  pass('cold_api_verifier_fetches_real_jwks_once')
  stage = 'cached_jwks'
  for (let i = 0; i < 3; i++) await api('/api/auth/me', admin.access_token, 200)
  ensure(await certCount('three_cached_requests') === 1, 'cached_fetch_count')
  pass('same_real_token_uses_jwks_cache_without_more_fetches')
  stage = 'real_signing_key_rotation'
  const realm = await (await administer('')).json()
  const providers = await (await administer('/components?type=org.keycloak.keys.KeyProvider')).json()
  const priority = Math.max(...providers.map(p => Number(p.config?.priority?.[0] || 0))) + 100
  await administer('/components', 'POST', { name: 'public-oidc-verification-rotation', parentId: realm.id,
    providerId: 'rsa-generated', providerType: 'org.keycloak.keys.KeyProvider',
    config: { priority: [String(priority)], active: ['true'], enabled: ['true'], algorithm: ['RS256'], keySize: ['2048'] } }, 201)
  const rotated = await realTokens('verification-admin')
  ensure(tokenPart(rotated.access_token, 0).kid !== tokenPart(admin.access_token, 0).kid, 'real_rotation_changed_kid')
  // The first JWKS fetch occurs after firstApiStarted. Stay below its unchanged
  // 60s TTL so the next fetch can prove unknown-kid refresh, not natural expiry.
  report.jwks_timing.rotation_api_started_at = new Date().toISOString()
  report.jwks_timing.elapsed_before_rotation_ms = Math.round(performance.now() - firstApiStarted)
  ensure(report.jwks_timing.elapsed_before_rotation_ms < 50000, 'rotation_cache_timing_precondition')
  await api('/api/auth/me', rotated.access_token, 200)
  report.jwks_timing.elapsed_after_rotation_ms = Math.round(performance.now() - firstApiStarted)
  ensure(report.jwks_timing.elapsed_after_rotation_ms < 55000, 'rotation_response_within_original_cache_ttl')
  ensure(await certCount('new_real_signing_key') === 2, 'unknown_key_forced_refresh_count')
  await api('/api/auth/me', admin.access_token, 200)
  ensure(await certCount('retained_previous_key') === 2, 'old_key_cache_count')
  pass('real_key_rotation_refreshes_jwks_and_retains_previous_valid_key')
  stage = 'cache_during_actual_idp_outage'
  ensure(tokenPart(rotated.access_token, 1).exp * 1000 > Date.now() + 90000, 'token_ttl_for_real_cache_wait')
  await pauseIdp()
  await api('/api/auth/me', rotated.access_token, 200)
  pass('cached_key_authenticates_while_actual_keycloak_is_paused')
  // Wait actual elapsed time past OIDCVerifier's unmodified 60-second cache.
  await sleep(61000)
  stage = 'expired_cache_during_actual_idp_outage'
  await api('/api/auth/me', rotated.access_token, 503)
  await api('/api/auth/me', emergencyKey, 200)
  pass('expired_jwks_fails_closed_503_while_emergency_key_remains_available')
  await unpauseIdp()
  stage = 'idp_recovery'
  await api('/api/auth/me', rotated.access_token, 200)
  ensure(await certCount('after_real_idp_recovery') >= 3, 'recovery_fetched_real_jwks')
  pass('actual_idp_recovery_fetches_jwks_and_restores_authentication')
  stage = 'real_token_rejections'
  const operator = await realTokens('verification-operator')
  const unassigned = await realTokens('verification-unassigned')
  const operatorIdentity = await (await api('/api/auth/me', operator.access_token, 200)).json()
  ensure(operatorIdentity.role === 'operator' && operatorIdentity.source === 'oidc', 'verified_operator_identity')
  await api('/api/auth/me', admin.id_token, 401)
  await api('/api/auth/me', unassigned.access_token, 401)
  await api('/api/admin/audit', operator.access_token, 403)
  pass('real_id_token_and_unassigned_access_token_rejected_operator_is_not_admin')
  stage = 'actual_document_unstarted_request'
  const document = read('source.md')
  ensure(createHash('sha256').update(document).digest('hex') === provenance.document_sha256, 'source_document_hash')
  const request = { goal: '添付したMultibot本番計画を確認する依頼を保存してください。今回は実行しません。',
    inputs: { files: [{ name: 'PRODUCTION_PLAN.md', content: document }] }, start: false }
  const options = { method: 'POST', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': 'real-oidc-document-admission' }, body: JSON.stringify(request) }
  const accepted = await (await api('/api/runs', operator.access_token, 202, options)).json()
  const replay = await (await api('/api/runs', operator.access_token, 202, options)).json()
  ensure(replay.run_id === accepted.run_id && accepted.status === 'created', 'unstarted_receipt_replay')
  const saved = await (await api('/api/runs/' + accepted.run_id, operator.access_token, 200)).json()
  ensure(saved.inputs.files[0].content === document && saved.status === 'created' && saved.usage.model_calls === 0, 'actual_source_saved_without_inference')
  pass('real_operator_saves_repository_document_start_false_and_replays_same_receipt')
  stage = 'actual_expired_token'
  const clients = await (await administer('/clients?clientId=' + clientId)).json()
  const client = await (await administer('/clients/' + clients[0].id)).json()
  await administer('/clients/' + client.id, 'PUT', { ...client, attributes: { ...client.attributes, 'access.token.lifespan': '30' } }, 204)
  const short = await realTokens('verification-viewer')
  const shortClaims = tokenPart(short.access_token, 1)
  ensure(shortClaims.exp - shortClaims.iat === 30, 'actual_short_token_lifetime')
  await api('/api/auth/me', short.access_token, 200)
  await administer('/clients/' + client.id, 'PUT', client, 204)
  await sleep(Math.max(0, shortClaims.exp * 1000 - Date.now() + 200))
  await api('/api/auth/me', short.access_token, 401)
  pass('real_issued_token_rejected_after_actual_expiry')
  stage = 'actual_token_logout'
  await api('/api/auth/logout', operator.access_token, 200, { method: 'POST' })
  await api('/api/auth/me', operator.access_token, 401)
  await api('/api/auth/me', rotated.access_token, 200)
  pass('logout_revokes_actual_token_without_revoking_other_identity')
  stage = 'no_model_or_queued_work'
  const db = await run('sqlite3', [`${root}/data/agentteam.sqlite`, "SELECT (SELECT count(*) FROM execution_jobs),(SELECT count(*) FROM events WHERE type IN ('model.called','model.failed')),(SELECT count(*) FROM runs),(SELECT count(*) FROM subject_admissions);"], { timeout: 10000 })
  ensure(db.stdout.trim() === '0|0|1|1', 'real_database_execution_or_admission_count')
  pass('sqlite_has_one_real_admission_zero_jobs_and_zero_model_events')
  stage = 'secret_free_evidence'
  await certCount('final')
  for (const name of ['server.private.log', 'keycloak.private.log']) {
    const log = read(name)
    ensure(secrets.every(secret => !log.includes(secret)), 'credential_found_in_service_log')
  }
  ensure(secrets.every(secret => !JSON.stringify(report).includes(secret)), 'credential_found_in_report')
  pass('report_and_service_logs_contain_no_issued_credentials_or_callback_codes')
  report.status = 'PASS'
} catch (error) {
  // Playwright exceptions can contain fill values. Keep them private, never
  // console, screenshots, CI artifacts or the public failure report.
  report.status = 'FAILED'; report.failure_stage = stage
  process.exitCode = 1
  privateFailure('failure.private.log', error)
} finally {
  report.cleanup = []
  async function cleanup(name, action, milliseconds) {
    try {
      await withinDeadline(action, milliseconds)
      report.cleanup.push({ name, status: 'PASS' })
    } catch (error) {
      report.status = 'FAILED'; report.cleanup_failed = true; process.exitCode = 1
      report.cleanup.push({ name, status: 'FAILED' })
      privateFailure(`cleanup-${name}.private.log`, error)
    }
    // A failed private log write must never prevent the next cleanup attempt.
    try { save('report.json', report) }
    catch { report.status = 'FAILED'; report.report_write_failed = true; process.exitCode = 1 }
  }
  // Each independent operation is attempted even if a predecessor fails.
  // Docker has its own 20s process timeout; the outer bound also handles a
  // command that does not settle after receiving its timeout signal.
  if (paused) await cleanup('keycloak-unpause', unpauseIdp, 21000)
  if (browser) await cleanup('browser-close', () => browser.close(), 15000)
  if (callback) await cleanup('callback-close', async () => {
    callback.unref()
    await new Promise((resolve, reject) => {
      callback.close(error => error ? reject(error) : resolve())
      callback.closeAllConnections()
    })
  }, 5000)
  report.finished_at = new Date().toISOString()
  try { save('report.json', report) }
  catch { report.status = 'FAILED'; report.report_write_failed = true; process.exitCode = 1 }
  console.log(JSON.stringify({ status: report.status, completed_checks: report.checks.length, failure_stage: report.failure_stage }))
  // A timed-out browser transport or callback must not retain this Node step
  // until the job timeout and prevent the safe report from being uploaded.
  // This does not claim process drainage; the workflow's always cleanup remains.
  if (report.cleanup_failed || report.report_write_failed) process.exit(1)
}

// Real Keycloak + OAuth2 Proxy + API + browser. No fabricated JWTs or mocked IdP.
// Issued passwords/tokens remain in private staging files and never in evidence.
import { chromium } from 'playwright-core'
import { createServer, request as httpRequest } from 'node:http'
import { randomBytes, createHash } from 'node:crypto'
import { readFileSync, writeFileSync, mkdirSync, renameSync } from 'node:fs'
import assert from 'node:assert/strict'

const root = process.env.OIDC_ROOT
if (!root) throw new Error('OIDC_ROOT is required')
const origin = 'http://127.0.0.1:8800'
const backend = 'http://127.0.0.1:8798'
const issuer = 'http://127.0.0.1:8801/realms/agentteam'
const passwords = JSON.parse(readFileSync(`${root}/staging-users.json`, 'utf8'))
const clientSecret = readFileSync(`${root}/client-secret`, 'utf8')
const accessPath = `${root}/security/access.json`
const originalAccess = JSON.parse(readFileSync(accessPath, 'utf8'))
const runId = 'run_1a09bfe4acdc8c36d5f'
const shots = `${root}/screenshots`
mkdirSync(shots, { recursive: true })
const checks = []
const errors = []
const tokens = {}
let restoreClient
let pending
const callback = createServer(async (req, res) => {
  const url = new URL(req.url, 'http://127.0.0.1:8802')
  if (url.pathname !== '/callback' || !pending || url.searchParams.get('state') !== pending.state) {
    res.writeHead(400).end('Invalid OAuth callback'); return
  }
  const operation = pending; pending = null
  try {
    const response = await fetch(`${issuer}/protocol/openid-connect/token`, {
      method: 'POST', body: new URLSearchParams({ grant_type: 'authorization_code', client_id: 'agentteam-login',
        client_secret: clientSecret, redirect_uri: 'http://127.0.0.1:8802/callback',
        code: url.searchParams.get('code'), code_verifier: operation.verifier }),
    })
    assert.equal(response.status, 200, 'actual authorization code exchange')
    const result = await response.json()
    res.writeHead(200, { 'Content-Type': 'text/plain', 'Cache-Control': 'no-store' }).end('Authorization verified. You can close this page.')
    operation.resolve(result)
  } catch { res.writeHead(502).end('Token exchange failed'); operation.reject(new Error('Actual IdP token exchange failed')) }
})
await new Promise(resolve => callback.listen(8802, '127.0.0.1', resolve))
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const saveAccess = data => { writeFileSync(accessPath + '.oidc-check', JSON.stringify(data), { mode: 0o600 }); renameSync(accessPath + '.oidc-check', accessPath) }
async function api(path, token, options = {}) {
  // Native fetch overrides Host on newer Node releases. The direct-backend drill
  // must preserve the real deployment Host, just as OAuth2 Proxy does.
  return new Promise((resolve, reject) => {
    const request = httpRequest(backend + path, { method: options.method || 'GET', headers: {
      Host: '127.0.0.1:8800', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers,
    } }, response => {
      const chunks = []
      response.on('data', chunk => chunks.push(chunk))
      response.on('end', () => resolve({ status: response.statusCode, json: async () => JSON.parse(Buffer.concat(chunks).toString()) }))
    })
    request.on('error', reject)
    request.end(options.body)
  })
}
async function login(page, name) {
  await page.locator('#username').fill(name)
  await page.locator('#password').fill(passwords[name])
  await page.locator('#kc-login').click()
}
async function realTokens(name) {
  const context = await browser.newContext()
  const page = await context.newPage()
  const verifier = randomBytes(32).toString('base64url')
  const state = randomBytes(24).toString('base64url')
  const result = new Promise((resolve, reject) => { pending = { verifier, state, resolve, reject } })
  const url = new URL(`${issuer}/protocol/openid-connect/auth`)
  url.search = new URLSearchParams({ client_id: 'agentteam-login', redirect_uri: 'http://127.0.0.1:8802/callback', response_type: 'code',
    scope: 'openid email profile', state, nonce: randomBytes(24).toString('base64url'), code_challenge_method: 'S256',
    code_challenge: createHash('sha256').update(verifier).digest('base64url') }).toString()
  await page.goto(url.toString())
  await login(page, name)
  const issued = await result
  await context.close()
  return issued
}
try {
  // Full deployed browser flow, including OAuth2 Proxy's state/nonce/PKCE checks.
  const context = await browser.newContext({ viewport: { width: 1440, height: 960 }, locale: 'ja-JP' })
  const page = await context.newPage()
  page.on('pageerror', error => errors.push(error.message))
  let actualCallback
  page.on('request', request => { if (request.url().startsWith(origin + '/oauth2/callback?')) actualCallback = request.url() })
  await page.goto(origin)
  await page.locator('#username').waitFor()
  await page.screenshot({ path: `${shots}/sso-login.png` })
  await login(page, 'forifor')
  await page.getByRole('button', { name: /^(ログアウト|Sign out)$/ }).waitFor()
  const identity = await (await page.request.get(origin + '/api/auth/me')).json()
  assert.equal(identity.role, 'admin'); assert.equal(identity.source, 'oidc')
  await page.goto(`${origin}/runs/${runId}`)
  await page.getByRole('heading', { level: 1 }).waitFor()
  await page.waitForFunction(() => [...document.querySelectorAll('.reveal')].every(el => getComputedStyle(el).opacity === '1'))
  await page.screenshot({ path: `${shots}/sso-run.png` })
  checks.push('Browser authorization code + S256 PKCE + nonce; real administrator; original saved artifact view')
  const cookies = await context.cookies(origin)
  const replay = await fetch(actualCallback, { redirect: 'manual' })
  assert.equal(replay.status, 403)
  checks.push('Replayed callback without its CSRF cookie is rejected')
  await page.getByRole('button', { name: /^(ログアウト|Sign out)$/ }).click()
  await page.locator('#username').waitFor()
  const oldCookie = cookies.map(c => `${c.name}=${c.value}`).join('; ')
  assert.equal((await fetch(origin + '/api/auth/me', { headers: { Cookie: oldCookie }, redirect: 'manual' })).status, 401)
  checks.push('Logout clears proxy and IdP sessions; copied pre-logout proxy cookie cannot regain API access')
  await context.close()

  // Obtain each access/ID token through a real browser authorization-code grant.
  for (const name of Object.keys(passwords)) tokens[name] = await realTokens(name)
  writeFileSync(`${root}/issued-tokens.json`, JSON.stringify(tokens), { mode: 0o600 })
  const admin = tokens.forifor.access_token
  const operator = tokens['verification-operator'].access_token
  const viewer = tokens['verification-viewer'].access_token
  for (const [name, role] of [['forifor', 'admin'], ['verification-operator', 'operator'], ['verification-viewer', 'viewer']]) {
    const response = await api('/api/auth/me', tokens[name].access_token)
    assert.equal(response.status, 200, name)
    assert.equal((await response.json()).role, role)
  }
  checks.push('Three actual IdP group memberships map to admin/operator/viewer')
  assert.equal((await api('/api/auth/me', tokens['verification-unassigned'].access_token)).status, 401)
  assert.equal((await api('/api/auth/me', tokens.forifor.id_token)).status, 401)
  assert.equal((await api('/api/auth/me', null, { headers: { 'X-Forwarded-User': 'forifor', 'X-Forwarded-Groups': '/agentteam-admin' } })).status, 401)
  checks.push('Unmapped membership, real ID token, and unsigned forwarded identity are rejected')
  assert.equal((await api('/api/auth/me', null, { headers: { 'X-Forwarded-Access-Token': admin } })).status, 200)
  assert.equal((await api('/api/auth/logout', null, { method: 'POST', headers: { 'X-Forwarded-Access-Token': operator } })).status, 403)
  checks.push('Forwarded access tokens require a signature; cookie/proxy mutations require same Origin')
  assert.equal((await api('/api/admin/audit', operator)).status, 403)
  assert.equal((await api('/api/runs', viewer, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })).status, 403)
  const operatorIdentity = await (await api('/api/auth/me', operator)).json()
  assert.equal((await api(`/api/runs/${runId}/access`, admin, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ subject: operatorIdentity.subject, permission: 'revoke' }) })).status, 200)
  assert.equal((await api(`/api/runs/${runId}`, operator)).status, 404)
  const grant = await api(`/api/runs/${runId}/access`, admin, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ subject: operatorIdentity.subject, permission: 'read' }) })
  assert.equal(grant.status, 200)
  assert.equal((await api(`/api/runs/${runId}`, operator)).status, 200)
  assert.equal((await api(`/api/runs/${runId}/cancel`, operator, { method: 'POST' })).status, 404)
  checks.push('Administrator-only endpoints, viewer mutations, per-run isolation and SSO read grants enforced')
  saveAccess({ ...originalAccess, oidc: { ...originalAccess.oidc, disabled_subjects: [operatorIdentity.subject] } })
  assert.equal((await api('/api/auth/me', operator)).status, 401)
  saveAccess(originalAccess)
  assert.equal((await api('/api/auth/me', operator)).status, 200)
  checks.push('Local SSO subject revocation applies on the next request, without waiting for token expiry')
  for (const change of [{ audience: 'agentteam-other-api' }, { issuer: originalAccess.oidc.issuer + '-other' }, { client_id: 'agentteam-other-client' }, { max_token_seconds: 30 }]) {
    saveAccess({ ...originalAccess, oidc: { ...originalAccess.oidc, ...change } })
    assert.equal((await api('/api/auth/me', admin)).status, 401)
  }
  saveAccess(originalAccess)
  checks.push('Real signed tokens rejected for wrong audience, issuer, authorized party or excessive lifetime')
  const parts = admin.split('.')
  const signature = Buffer.from(parts[2], 'base64url'); signature[0] ^= 1
  assert.equal((await api('/api/auth/me', [parts[0], parts[1], signature.toString('base64url')].join('.'))).status, 401)
  checks.push('One-bit corruption of an actually issued signature is rejected')
  assert.equal((await api('/api/auth/logout', operator, { method: 'POST' })).status, 200)
  assert.equal((await api('/api/auth/me', operator)).status, 401)
  assert.equal((await api('/api/auth/me', admin)).status, 200)
  checks.push('API logout revokes the actual access token without invalidating another user')
  // Exercise actual issuer key rotation and actual time expiry. Administration
  // uses the private bootstrap account of this disposable local IdP only.
  const adminEnv = Object.fromEntries(readFileSync(`${root}/keycloak.env`, 'utf8').trim().split('\n').map(line => {
    const i = line.indexOf('='); return [line.slice(0, i), line.slice(i + 1)]
  }))
  const adminResponse = await fetch('http://127.0.0.1:8801/realms/master/protocol/openid-connect/token', { method: 'POST', body: new URLSearchParams({
    grant_type: 'password', client_id: 'admin-cli', username: adminEnv.KC_BOOTSTRAP_ADMIN_USERNAME, password: adminEnv.KC_BOOTSTRAP_ADMIN_PASSWORD,
  }) })
  assert.equal(adminResponse.status, 200, 'staging IdP administration')
  const idpAdmin = (await adminResponse.json()).access_token
  const administer = (path, method = 'GET', body) => fetch('http://127.0.0.1:8801/admin/realms/agentteam' + path, {
    method, headers: { Authorization: `Bearer ${idpAdmin}`, 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined,
  })
  const realm = await (await administer('')).json()
  const providers = await (await administer('/components?type=org.keycloak.keys.KeyProvider')).json()
  const priority = Math.max(...providers.map(p => Number(p.config?.priority?.[0] || 0))) + 100
  assert.equal((await administer('/components', 'POST', {
    name: 'agentteam-verification-' + randomBytes(6).toString('hex'), parentId: realm.id, providerId: 'rsa-generated',
    providerType: 'org.keycloak.keys.KeyProvider', config: { priority: [String(priority)], active: ['true'], enabled: ['true'], algorithm: ['RS256'], keySize: ['2048'] },
  })).status, 201)
  const rotated = await realTokens('forifor')
  const kid = token => JSON.parse(Buffer.from(token.split('.')[0], 'base64url').toString()).kid
  assert.notEqual(kid(rotated.access_token), kid(admin), 'issuer generated a new signing key')
  assert.equal((await api('/api/auth/me', rotated.access_token)).status, 200)
  assert.equal((await api('/api/auth/me', admin)).status, 200)
  checks.push('Actual Keycloak RSA key rotation refreshes JWKS; valid tokens signed with the retained previous key still work')
  const clients = await (await administer('/clients?clientId=agentteam-login')).json()
  const client = await (await administer('/clients/' + clients[0].id)).json()
  restoreClient = async () => { assert.equal((await administer('/clients/' + client.id, 'PUT', client)).status, 204) }
  assert.equal((await administer('/clients/' + client.id, 'PUT', { ...client, attributes: { ...client.attributes, 'access.token.lifespan': '30' } })).status, 204)
  const short = await realTokens('verification-viewer')
  assert.equal((await api('/api/auth/me', short.access_token)).status, 200)
  const claims = JSON.parse(Buffer.from(short.access_token.split('.')[1], 'base64url').toString())
  assert.equal(claims.exp - claims.iat, 30)
  await restoreClient(); restoreClient = null
  await new Promise(resolve => setTimeout(resolve, Math.max(0, claims.exp * 1000 - Date.now() + 100)))
  assert.equal((await api('/api/auth/me', short.access_token)).status, 401)
  checks.push('A real 30-second IdP access token is accepted before expiry and rejected after actual elapsed time')
  for (const logName of ['server.log', 'proxy-sanitized.log']) {
    const log = readFileSync(`${root}/${logName}`, 'utf8')
    for (const issued of [...Object.values(tokens), rotated, short]) {
      for (const key of ['access_token', 'id_token', 'refresh_token']) assert.equal(log.includes(issued[key]), false, 'token-free logs')
    }
    assert.equal(log.includes(new URL(actualCallback).searchParams.get('code')), false, 'callback-code-free logs')
  }
  checks.push('Application and sanitized proxy logs contain none of the actual issued access/ID/refresh tokens or callback code')
  assert.equal(errors.length, 0, 'browser JavaScript errors')
  const result = { recorded_at: new Date().toISOString(), keycloak: '26.7.3', oauth2_proxy: '7.15.4', checks, page_errors: errors,
    grant_type: 'authorization_code', pkce: 'S256', direct_access_grants: false, fake_provider: false, passwords_or_tokens_in_evidence: false }
  writeFileSync(`${root}/oidc-smoke.json`, JSON.stringify(result, null, 2) + '\n')
  console.log(JSON.stringify({ passed: checks.length, page_errors: errors }))
} catch (error) {
  const failure = { completed_checks: checks, location: error.stack?.match(/oidc-smoke\.mjs:\d+:\d+/)?.[0],
    message: error.message.split('\n')[0], actual: typeof error.actual === 'number' ? error.actual : undefined,
    expected: typeof error.expected === 'number' ? error.expected : undefined }
  writeFileSync(`${root}/oidc-failure-${Date.now()}.json`, JSON.stringify(failure, null, 2))
  console.error('OIDC integration failed:', JSON.stringify(failure))
  process.exitCode = 1
} finally {
  if (restoreClient) await restoreClient()
  saveAccess(originalAccess)
  await browser.close()
  await new Promise(resolve => callback.close(resolve))
}

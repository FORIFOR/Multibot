import { Fragment, useEffect, useRef, useState, type ReactNode } from 'react'
import { getLang } from '../lib/i18n'
import { bindBrowserSession, broadcastSessionChange, browserPrincipalKey, browserSessionActive, clearBrowserSession, suspendBrowserSession, SESSION_CHANGE_KEY, SESSION_TAB_ID } from '../lib/browser-session'

export interface Identity { subject: string; role: 'admin' | 'operator' | 'viewer' | 'auditor'; organization: string | null; display_name?: string; source?: string }

const AUTH_REQUEST_TIMEOUT_MS = 15000
// A tab may disappear without sending its completion notification. Allow longer
// than login/logout's request deadline, then require an explicit new sign-in.
const PEER_AUTH_TIMEOUT_MS = 20000

export default function AuthGate({ children }: { children: (identity: Identity, secured: boolean) => ReactNode }) {
  const [identity, setIdentity] = useState<Identity | null>(null)
  const [secured, setSecured] = useState(false)
  const [ssoLogin, setSsoLogin] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [token, setToken] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const ja = getLang() !== 'en'
  const authVersion = useRef(0)
  const signingOut = useRef(false)
  const pendingPeers = useRef(new Set<string>())
  useEffect(() => {
    let alive = true
    const peers = pendingPeers.current
    const peerTimers = new Map<string, ReturnType<typeof setTimeout>>()
    const load = async () => {
      const version = ++authVersion.current
      setLoading(true)
      try {
        const status = await fetch('/api/auth/status', { cache: 'no-store', signal: AbortSignal.timeout(AUTH_REQUEST_TIMEOUT_MS) })
        if (!status.ok) throw new Error('connection')
        const settings = await status.json()
        const response = await fetch('/api/auth/me', { cache: 'no-store', signal: AbortSignal.timeout(AUTH_REQUEST_TIMEOUT_MS) })
        const next = response.ok ? await response.json() : null
        if (!alive || version !== authVersion.current) return
        setSecured(settings.enabled)
        setSsoLogin(settings.sso_login_url)
        if (next) { const changed = bindBrowserSession(next, settings.enabled); if (changed) broadcastSessionChange(); setIdentity(next); setError('') }
        else if (response.status === 401) { clearBrowserSession(); setIdentity(null) }
        else throw new Error('connection')
      } catch {
        if (!alive || version !== authVersion.current) return
        suspendBrowserSession(); setIdentity(null)
        setError(ja ? 'サーバーへ接続できません。再読込してください。' : 'Cannot connect to the server. Reload to retry.')
      } finally { if (alive && version === authVersion.current) setLoading(false) }
    }
    const expire = (message: string) => {
      authVersion.current++
      clearBrowserSession(); setIdentity(null); setToken(''); setBusy(false); setLoading(false); setError(message)
    }
    const expired = () => { expire(ja ? 'セッションが終了しました。再ログインしてください。' : 'Session ended. Sign in again.'); broadcastSessionChange() }
    const peerSequences = new Map<string, number>()
    const changed = (message: { sender?: string; pending?: boolean; sequence?: number }) => {
      if (message.sender === SESSION_TAB_ID) return
      const sender = message.sender || 'unknown'
      const sequence = message.sequence || 0
      if (sequence && sequence <= (peerSequences.get(sender) || 0)) return
      peerSequences.set(sender, sequence)
      clearTimeout(peerTimers.get(sender))
      peerTimers.delete(sender)
      if (message.pending) {
        pendingPeers.current.add(sender)
        const timer = setTimeout(() => {
          if (!alive || peerTimers.get(sender) !== timer) return
          peerTimers.delete(sender); pendingPeers.current.delete(sender)
          expire(ja ? '別のタブでのログイン確認が終了しませんでした。再ログインしてください。' : 'Sign-in in another tab did not finish. Sign in again.')
          setLoading(signingOut.current || pendingPeers.current.size > 0)
        }, PEER_AUTH_TIMEOUT_MS)
        peerTimers.set(sender, timer)
      }
      else pendingPeers.current.delete(sender)
      expire(ja ? '別のタブでログイン状態が変わりました。再ログインしてください。' : 'Sign-in changed in another tab. Sign in again.')
      setLoading(signingOut.current || pendingPeers.current.size > 0)
    }
    const signedOut = () => { signingOut.current = true; expire(''); setLoading(true) }
    const signOutFailed = () => { signingOut.current = false; setLoading(pendingPeers.current.size > 0); setError(ja ? 'この画面のデータは消去しましたが、サーバーのログアウトを確認できません。接続を確認し、再ログインしてログアウトし直してください。' : 'Local data was cleared, but server sign-out could not be confirmed. Check the connection, sign in, then sign out again.') }
    const storage = (event: StorageEvent) => { if (event.key === SESSION_CHANGE_KEY) { try { changed(JSON.parse(event.newValue || '{}')) } catch { changed({}) } } }
    const visible = () => { if (document.visibilityState === 'visible' && browserSessionActive()) void load() }
    let channel: BroadcastChannel | null = null
    try { channel = new BroadcastChannel(SESSION_CHANGE_KEY); channel.onmessage = event => changed(event.data || {}) } catch { /* storage and visibility events remain available */ }
    void load()
    window.addEventListener('agentteam:unauthorized', expired)
    window.addEventListener('agentteam:signout', signedOut)
    window.addEventListener('agentteam:signout-failed', signOutFailed)
    window.addEventListener('storage', storage)
    document.addEventListener('visibilitychange', visible)
    return () => {
      alive = false; authVersion.current++
      for (const timer of peerTimers.values()) clearTimeout(timer)
      peerTimers.clear(); peers.clear()
      channel?.close()
      window.removeEventListener('agentteam:unauthorized', expired)
      window.removeEventListener('agentteam:signout', signedOut)
      window.removeEventListener('agentteam:signout-failed', signOutFailed)
      window.removeEventListener('storage', storage)
      document.removeEventListener('visibilitychange', visible)
    }
  }, [ja])
  if (loading) return <main className="main" role="status">{ja ? '接続を確認しています…' : 'Connecting…'}</main>
  if (identity) return <Fragment key={browserPrincipalKey(identity, secured)}>{children(identity, secured)}</Fragment>
  const keyForm = <form className="stack" onSubmit={async event => {
      event.preventDefault(); setBusy(true); setError('')
      const version = ++authVersion.current
      broadcastSessionChange(true)
      try {
        const response = await fetch('/api/auth/login', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ token }), signal: AbortSignal.timeout(AUTH_REQUEST_TIMEOUT_MS) })
        if (!response.ok) throw new Error(response.status === 429 ? (ja ? 'しばらく待って再試行してください。' : 'Wait a moment before retrying.') : (ja ? 'ログインできませんでした。アクセスキーを確認してください。' : 'Sign-in failed. Check your access key.'))
        const next = await response.json()
        if (version !== authVersion.current) {
          // Set-Cookie may already have replaced the shared browser session. Never keep another identity's workspace.
          authVersion.current++; clearBrowserSession(); broadcastSessionChange()
          setIdentity(null); setToken(''); setBusy(false); setLoading(signingOut.current || pendingPeers.current.size > 0)
          setError(ja ? '別のログイン操作と重なりました。再ログインしてください。' : 'Another sign-in overlapped. Sign in again.')
          return
        }
        clearBrowserSession(); bindBrowserSession(next, secured); broadcastSessionChange()
        setIdentity(next); setToken('')
      } catch (e) {
        // A failed/expired response can still have applied Set-Cookie before its body was read.
        authVersion.current++; clearBrowserSession(); broadcastSessionChange()
        setIdentity(null); setToken(''); setBusy(false); setLoading(signingOut.current || pendingPeers.current.size > 0)
        setError(e instanceof Error ? e.message : String(e))
      } finally { if (version === authVersion.current) setBusy(false) }
    }}>
      <label htmlFor="access-key">{ja ? 'アクセスキー' : 'Access key'}</label>
      <input id="access-key" className="input" type="password" autoComplete="current-password" value={token} onChange={event => setToken(event.target.value)} required minLength={32} maxLength={256} />
      <button className="btn signal" disabled={busy || !secured}>{busy ? (ja ? '確認中…' : 'Signing in…') : (ja ? 'ログイン' : 'Sign in')}</button>
    </form>
  return <main className="main" style={{ maxWidth: 480, paddingTop: 96 }}>
    <h1>Multibot</h1>
    {ssoLogin ? <>
      <p className="lede">{ja ? 'アカウントでログインして、チームへの依頼を始めましょう。' : 'Sign in to start working with your team.'}</p>
      <a className="btn signal" href={ssoLogin}>{ja ? 'ログインして始める' : 'Sign in to get started'}</a>
      <details style={{ marginTop: 24 }}><summary>{ja ? 'アクセスキーでログイン' : 'Sign in with an access key'}</summary>
        <p>{ja ? 'アクセスキーを受け取っている場合はこちらからログインできます。' : 'Use this option if you have been issued an access key.'}</p>{keyForm}
      </details>
    </> : <>
      <p className="lede">{ja ? '管理者から受け取ったアクセスキーでログインしてください。' : 'Sign in with the access key issued by your administrator.'}</p>
      {keyForm}
    </>}
    {error && <p role="alert" className="err">{error}</p>}
  </main>
}

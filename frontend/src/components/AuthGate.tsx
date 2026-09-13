import { useEffect, useState, type ReactNode } from 'react'
import { getLang } from '../lib/i18n'

export interface Identity { subject: string; role: 'admin' | 'operator' | 'viewer'; organization: string | null; display_name?: string; source?: string }

export default function AuthGate({ children }: { children: (identity: Identity, secured: boolean) => ReactNode }) {
  const [identity, setIdentity] = useState<Identity | null>(null)
  const [secured, setSecured] = useState(false)
  const [ssoLogin, setSsoLogin] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [token, setToken] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const ja = getLang() !== 'en'
  useEffect(() => {
    const load = async () => {
      try {
        const status = await fetch('/api/auth/status')
        if (!status.ok) throw new Error('connection')
        const settings = await status.json()
        setSecured(settings.enabled)
        setSsoLogin(settings.sso_login_url)
        const response = await fetch('/api/auth/me')
        if (response.ok) setIdentity(await response.json())
        else if (response.status !== 401) throw new Error('connection')
      } catch { setError(ja ? 'サーバーへ接続できません。再読込してください。' : 'Cannot connect to the server. Reload to retry.') }
      finally { setLoading(false) }
    }
    const expired = () => { setIdentity(null); setToken(''); setError(ja ? 'セッションが終了しました。再ログインしてください。' : 'Session ended. Sign in again.') }
    void load()
    window.addEventListener('agentteam:unauthorized', expired)
    return () => window.removeEventListener('agentteam:unauthorized', expired)
  }, [ja])
  if (loading) return <main className="main" role="status">{ja ? '接続を確認しています…' : 'Connecting…'}</main>
  if (identity) return children(identity, secured)
  return <main className="main" style={{ maxWidth: 480, paddingTop: 96 }}>
    <h1>Agent Team</h1>
    {ssoLogin && <><p className="lede">{ja ? '組織のアカウントでログインしてください。権限がない場合は管理者に確認してください。' : 'Sign in with your organization account. Contact your administrator if access is denied.'}</p><a className="btn signal" href={ssoLogin}>{ja ? '組織アカウントでログイン' : 'Sign in with SSO'}</a></>}
    <p className="lede">{ja ? '管理者から受け取ったアクセスキーでログインしてください。' : 'Sign in with the access key issued by your administrator.'}</p>
    <form className="stack" onSubmit={async event => {
      event.preventDefault(); setBusy(true); setError('')
      try {
        const response = await fetch('/api/auth/login', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ token }) })
        if (!response.ok) throw new Error(response.status === 429 ? (ja ? 'しばらく待って再試行してください。' : 'Wait a moment before retrying.') : (ja ? 'ログインできませんでした。アクセスキーを確認してください。' : 'Sign-in failed. Check your access key.'))
        setIdentity(await response.json()); setToken('')
      } catch (e) { setError(e instanceof Error ? e.message : String(e)) }
      finally { setBusy(false) }
    }}>
      <label htmlFor="access-key">{ja ? 'アクセスキー' : 'Access key'}</label>
      <input id="access-key" className="input" type="password" autoComplete="current-password" value={token} onChange={event => setToken(event.target.value)} required minLength={32} maxLength={256} />
      <button className="btn signal" disabled={busy || !secured}>{busy ? (ja ? '確認中…' : 'Signing in…') : (ja ? 'ログイン' : 'Sign in')}</button>
      {error && <p role="alert" className="err">{error}</p>}
    </form>
  </main>
}

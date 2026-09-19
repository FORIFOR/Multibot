import { getLang, setLang } from './lib/i18n'
import { useEffect, useState } from 'react'
import { api, type Approval } from './lib/api'
import { Link, usePath, getRunId } from './lib/router'
import Home from './pages/Home'
import RunView from './pages/Workroom'
import Settings from './pages/Settings'
import Welcome from './pages/Welcome'
import Operations from './pages/Operations'
import AuthGate, { type Identity } from './components/AuthGate'

export default function App() {
  return <AuthGate>{(identity, secured) => <Workspace identity={identity} secured={secured} />}</AuthGate>
}

function Workspace({ identity, secured }: { identity: Identity; secured: boolean }) {
  const [path, nav] = usePath()
  const [pending, setPending] = useState<Approval[]>([])
  const [version, setVersion] = useState<string>("")
  useEffect(() => { if (identity.role !== 'auditor') api.health().then(h => setVersion(h.version)).catch(() => { /* offline */ }) }, [identity.role])
  useEffect(() => {
    if (identity.role === 'auditor') return
    let alive = true
    const tick = async () => { try { const a = await api.approvals('pending'); if (alive) setPending(a) } catch { /* offline */ } }
    tick()
    const id = setInterval(tick, 5000)
    return () => { alive = false; clearInterval(id) }
  }, [path, identity.role])
  const runId = getRunId(path)
  return (
    <div className="shell">
      <header className="top">
        <Link to="/" nav={nav} className="brand">Agent Team</Link>
        <nav className="nav">
          {secured && <><span className="muted small account-identity">{identity.organization} · {identity.display_name || identity.subject}</span><button className="langbtn" onClick={async () => { const response = await fetch('/api/auth/logout', { method: 'POST' }); const result = response.ok ? await response.json() : {}; window.location.assign(result.redirect || '/') }}>{getLang() === 'en' ? 'Sign out' : 'ログアウト'}</button></>}
          {identity.role !== 'auditor' && <Link to="/" nav={nav} className={path === '/' ? 'active' : ''}>{getLang() === "en" ? "Ask" : "お願いする"}</Link>}
          {identity.role === 'admin' && <Link to="/settings" nav={nav} className={path.startsWith('/settings') ? 'active' : ''}>{getLang() === "en" ? "My team" : "マイチーム"}</Link>}
          {pending.length > 0 && <Link to={`/runs/${pending[0].run_id}?tab=approvals`} nav={nav} className="active" >{getLang() === "en" ? "Needs approval" : "確認が必要"} {pending.length}</Link>}
          <details className="app-more">
            <summary>{getLang() === 'en' ? 'More' : 'その他'}</summary>
            <div className="app-more-content">
          {(identity.role === 'admin' || identity.role === 'auditor') && <Link to="/operations" nav={nav} className={path.startsWith('/operations') ? 'active' : ''}>{getLang() === 'en' ? 'Operations' : '運用状況'}</Link>}
              <a href="https://github.com/FORIFOR/Multibot" target="_blank" rel="noreferrer">GitHub</a>
              <button className="langbtn" title="Language" onClick={() => { setLang(getLang() === 'en' ? 'ja' : 'en'); window.location.reload() }}>{getLang() === 'en' ? '日本語' : 'English'}</button>
              <small>{version ? `v${version}` : ''} · local-first</small>
            </div>
          </details>
        </nav>
      </header>
      <main className={'main' + (runId ? ' wide' : '')}>
        {identity.role === 'auditor' || (path.startsWith('/operations') && identity.role === 'admin') ? <Operations /> : runId ? <RunView key={path} runId={runId} nav={nav} /> : path.startsWith('/settings') && identity.role === 'admin' ? <Settings /> : path.startsWith('/welcome') ? <Welcome nav={nav} canConfigure={identity.role === 'admin'} /> : <Home nav={nav} readOnly={identity.role === 'viewer'} canConfigure={identity.role === 'admin'} />}
      </main>
    </div>
  )
}

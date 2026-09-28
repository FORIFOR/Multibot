import { getLang, setLang } from './lib/i18n'
import { useEffect, useState } from 'react'
import { api, type Approval } from './lib/api'
import { Link, usePath, getRunId } from './lib/router'
import Home from './pages/Home'
import WorkList from './pages/WorkList'
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
  const en = getLang() === 'en'
  return (
    <div className="shell shell-side">
      <aside className="top side" aria-label={en ? 'Main menu' : 'メインメニュー'}>
        <Link to="/runs" nav={nav} className="brand">Agent Team</Link>
        {secured && <div className="side-org"><span className="side-org-mark" aria-hidden="true">{(identity.organization || '?').slice(0, 1)}</span><span><strong>{identity.organization}</strong><small>{identity.display_name || identity.subject}</small></span></div>}
        {identity.role !== 'auditor' && <Link to="/" nav={nav} className="side-new">＋ {en ? 'New request' : '新しいお願い'}</Link>}
        <nav className="nav side-nav">
          {identity.role !== 'auditor' && <Link to="/" nav={nav} className={path === '/' ? 'active' : ''}>{en ? 'Ask' : 'お願いする'}</Link>}
          {identity.role !== 'auditor' && <Link to="/runs" nav={nav} className={path.startsWith('/runs') ? 'active' : ''}>{en ? 'Work' : '作業一覧'}{pending.length > 0 && <span className="side-badge" aria-label={en ? `${pending.length} need approval` : `確認が必要 ${pending.length}件`}>{pending.length}</span>}</Link>}
          {identity.role === 'admin' && <Link to="/settings" nav={nav} className={path.startsWith('/settings') ? 'active' : ''}>{en ? 'My team' : 'マイチーム'}</Link>}
          {(identity.role === 'admin' || identity.role === 'auditor') && <Link to="/operations" nav={nav} className={path.startsWith('/operations') ? 'active' : ''}>{en ? 'Operations' : '運用状況'}</Link>}
        </nav>
        {pending.length > 0 && <Link to={`/runs/${pending[0].run_id}?tab=approvals`} nav={nav} className="side-attention"><strong>{en ? 'Needs your approval' : 'あなたの確認待ち'}</strong><span>{en ? `${pending.length} request(s) are waiting` : `${pending.length}件のお願いが待っています`}</span></Link>}
        <div className="side-foot">
          <button className="langbtn" title="Language" onClick={() => { setLang(en ? 'ja' : 'en'); window.location.reload() }}>{en ? '日本語' : 'English'}</button>
          <a href="https://github.com/FORIFOR/Multibot" target="_blank" rel="noreferrer">GitHub</a>
          {secured && <button className="langbtn" onClick={async () => { const response = await fetch('/api/auth/logout', { method: 'POST' }); const result = response.ok ? await response.json() : {}; window.location.assign(result.redirect || '/') }}>{en ? 'Sign out' : 'ログアウト'}</button>}
          {version && <small>v{version}</small>}
        </div>
      </aside>
      <main className={'main' + (runId ? ' wide' : '')}>
        {identity.role === 'auditor' || (path.startsWith('/operations') && identity.role === 'admin') ? <Operations /> : runId ? <RunView key={path} runId={runId} nav={nav} /> : path.startsWith('/settings') && identity.role === 'admin' ? <Settings /> : path.startsWith('/welcome') ? <Welcome nav={nav} canConfigure={identity.role === 'admin'} /> : path.split('?')[0] === '/runs' ? <WorkList nav={nav} readOnly={identity.role === 'viewer'} /> : <Home nav={nav} readOnly={identity.role === 'viewer'} canConfigure={identity.role === 'admin'} />}
      </main>
    </div>
  )
}

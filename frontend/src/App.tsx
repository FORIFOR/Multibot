import { t, getLang, setLang } from './lib/i18n'
import { useEffect, useState } from 'react'
import { api, type Approval } from './lib/api'
import { Link, usePath } from './lib/router'
import Home from './pages/Home'
import RunView from './pages/RunView'
import Settings from './pages/Settings'

export default function App() {
  const [path, nav] = usePath()
  const [pending, setPending] = useState<Approval[]>([])
  useEffect(() => {
    let alive = true
    const tick = async () => { try { const a = await api.approvals('pending'); if (alive) setPending(a) } catch { /* offline */ } }
    tick()
    const id = setInterval(tick, 5000)
    return () => { alive = false; clearInterval(id) }
  }, [path])
  const runMatch = path.match(/^\/runs\/([^/]+)/)
  return (
    <div className="shell">
      <header className="top">
        <Link to="/" nav={nav} className="brand">Agent Team <small>v0.1 · local-first</small></Link>
        <nav className="nav">
          <Link to="/" nav={nav} className={path === '/' ? 'active' : ''}>{t("依頼")}</Link>
          <Link to="/settings" nav={nav} className={path.startsWith('/settings') ? 'active' : ''}>{t("設定")}</Link>
          {pending.length > 0 && <Link to={`/runs/${pending[0].run_id}?tab=approvals`} nav={nav} className="active" >承認待ち {pending.length}</Link>}
          <a href="https://github.com/FORIFOR/Multibot" target="_blank" rel="noreferrer" title="GitHub">★ GitHub</a>
          <button className="langbtn" title="Language" onClick={() => { setLang(getLang() === 'en' ? 'ja' : 'en'); window.location.reload() }}>{getLang() === 'en' ? '日本語' : 'EN'}</button>
        </nav>
      </header>
      <main className={'main' + (runMatch ? ' wide' : '')}>
        {runMatch ? <RunView runId={runMatch[1]} nav={nav} /> : path.startsWith('/settings') ? <Settings /> : <Home nav={nav} />}
      </main>
    </div>
  )
}

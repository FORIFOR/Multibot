import { useEffect, useState } from 'react'
import { api, fmtDate, type Run } from '../lib/api'
import { getLang } from '../lib/i18n'
import { statusLabel } from '../lib/journey'
import { Link } from '../lib/router'
import '../journey.css'

const filters = ['all', 'active', 'attention', 'completed'] as const
type Filter = typeof filters[number]
export function workFilter(value: string | null): Filter {
  return filters.includes(value as Filter) ? value as Filter : 'all'
}
function matches(run: Run, filter: Filter) {
  if (filter === 'active') return ['created', 'queued', 'planning', 'running'].includes(run.status)
  if (filter === 'attention') return ['approval_required', 'blocked'].includes(run.status)
  if (filter === 'completed') return run.status === 'completed'
  return true
}
export default function WorkList({ nav, readOnly = false }: { nav: (path: string) => void; readOnly?: boolean }) {
  const en = getLang() === 'en'
  const filter = workFilter(new URLSearchParams(location.search).get('filter'))
  const [query, setQuery] = useState(() => { try { return sessionStorage.getItem('work-list-search') || '' } catch { return '' } })
  const search = (value: string) => { setQuery(value); try { sessionStorage.setItem('work-list-search', value) } catch { /* Search still works without storage. */ } }
  const [runs, setRuns] = useState<Run[]>([])
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState(false)
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    let alive = true, fetching = false
    const refresh = async () => {
      if (fetching) return
      fetching = true
      try { const value = await api.runs(); if (alive) { setRuns(value); setLoaded(true); setError(false) } }
      catch { if (alive) setError(true) }
      finally { fetching = false }
    }
    void refresh()
    const timer = setInterval(() => { if (!document.hidden) void refresh() }, 5000)
    const visible = () => { if (!document.hidden) void refresh() }
    document.addEventListener('visibilitychange', visible)
    return () => { alive = false; clearInterval(timer); document.removeEventListener('visibilitychange', visible) }
  }, [retry])
  const labels = en ? ['All', 'In progress', 'Awaiting review', 'Completed'] : ['全て', '進行中', '確認待ち', '完了']
  const visible = runs.filter(run => matches(run, filter) && run.goal.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()))
  return <section className="work-list" aria-labelledby="work-list-title">
    <header className="work-list-heading"><div><p className="work-list-eyebrow">{en ? 'YOUR TEAM’S WORK' : 'チームにお願いした作業'}</p><h1 id="work-list-title">{en ? 'Work' : '作業一覧'}</h1><p>{en ? 'Open a request to follow its team conversation and results.' : '作業を選ぶと、そのチームのやり取りと成果物を確認できます。'}</p></div>{!readOnly && <Link to="/" nav={nav} className="btn signal">{en ? 'New request' : '新しくお願いする'}</Link>}</header>
    <div className="work-search"><label><span className="sr-only">{en ? 'Search requests' : '作業を検索'}</span><input type="search" className="input" value={query} onChange={event => search(event.target.value)} placeholder={en ? 'Search requests…' : '作業を検索…'} /></label>{query && <button type="button" className="btn ghost" onClick={() => search('')}>{en ? 'Clear' : 'クリア'}</button>}</div>
    <nav className="work-filters" aria-label={en ? 'Filter work' : '作業の絞り込み'}>{filters.map((value, i) => <a key={value} href={`/runs?filter=${value}`} aria-current={value === filter ? 'page' : undefined} onClick={event => { if(event.button || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return; event.preventDefault(); nav(`/runs?filter=${value}`) }}>{labels[i]}<span>{loaded ? runs.filter(run => matches(run, value)).length : '—'}</span></a>)}</nav>
    <p className="work-list-note">{en ? 'Showing up to 50 recent requests you can access. Counts refer to this list. ' : '閲覧できる直近50件が対象です。件数はこの一覧の範囲で表示します。'}{filter === 'attention' ? (en ? 'Requests awaiting your approval or blocked by a prerequisite.' : 'あなたの承認、または作業を進めるための条件確認が必要です。') : filter === 'completed' ? (en ? 'Only requests recorded as completed. Inspect their results before use.' : '完了が記録された作業です。成果物の内容を確認してからご利用ください。') : (en ? 'Interrupted, failed and cancelled requests remain under All with their recorded status.' : '中断・失敗・取消・部分完了は「全て」に、実際の状態で表示します。')}</p>
    {error && <p className="work-warning" role="alert">{en ? 'Could not refresh. Displayed information may be out of date.' : '最新の一覧を取得できません。表示内容が古い可能性があります。'} <button className="btn ghost" onClick={() => setRetry(value => value + 1)}>{en ? 'Retry' : '再読み込み'}</button></p>}
    {!loaded && !error && <p role="status">{en ? 'Loading work…' : '作業を読み込んでいます…'}</p>}
    {loaded && <><p className="work-list-count" role="status">{labels[filters.indexOf(filter)]} · {visible.length}{en ? ' requests' : '件'}</p><ul className="work-items">{visible.map(run => <li key={run.run_id}><Link to={`/runs/${run.run_id}?view=conversation&from=${filter}`} nav={nav} className="work-item"><div className="work-item-main"><span className={'tag status-' + run.status}>{statusLabel(run.status, en ? 'en' : 'ja')}</span><h2 title={run.goal}>{run.goal}</h2><time dateTime={run.created_at}>{fmtDate(run.created_at)}</time>{run.provider_kind === 'fake' && <span className="tag fake">{en ? 'Test' : 'テスト'}</span>}</div><span className="work-item-open">{en ? 'Team conversation' : 'チームのやり取り'} <span aria-hidden="true">→</span></span></Link></li>)}</ul>{!visible.length && <div className="work-list-empty"><h2>{query ? (en ? 'No matching requests' : '一致する作業はありません') : (en ? 'No requests here yet' : 'この状態の作業はありません')}</h2><p>{en ? 'Choose another filter or start a new request.' : '別の状態に切り替えるか、新しくチームにお願いできます。'}</p></div>}</>}
  </section>
}

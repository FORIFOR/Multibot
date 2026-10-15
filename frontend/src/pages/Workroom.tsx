import { botName } from '../lib/journey'
import { useCallback, useEffect, useRef, useState, lazy, Suspense } from 'react'
import type { FormEvent } from 'react'
import { api, browserApiUrl, money, fmtTime, type RunDetail, type ChatMessage, type Artifact, type Event, type Approval } from '../lib/api'
import { getLang } from '../lib/i18n'
import { botActivity, botStateLabel } from '../lib/bot-presentation'
import { friendlyWorkText, coordinatorPlanned, outcomeLabel, friendlyReason, teamOrder, defaultPanel, requestedPanel, resultFiles, statusLabel, stateTone, roleLabel, isSettled, type JourneyPanel } from '../lib/journey'
import { Link } from '../lib/router'
import { readRequestDraft, saveRequestDraft } from '../lib/request-draft'
import { workFilter } from './WorkList'
import BotAvatar from '../components/BotAvatar'
import Markdown from '../components/Markdown'
import ArtifactWorkbench from '../components/ArtifactWorkbench'
import { WorkProgress } from '../components/WorkProgress'
import TeamConversation from '../components/TeamConversation'
import '../journey.css'
import '../welcome.css'
import '../workroom-refinement.css'

// Full audit tools are preserved, but loaded only when the user asks for them.
const Inspector = lazy(() => import('./RunView'))
const say = (ja: string, en: string) => getLang() === 'en' ? en : ja
const WORKROOM_READ_TIMEOUT_MS = 15000
const ARTIFACT_READ_TIMEOUT_MS = 15000
// A failed or unverified record is not "checked": the file list and status line must say which it is.
// Only the latest record of each kind counts; a later review of the same bytes supersedes an earlier one.
type CheckState = 'none' | 'pass' | 'concern'
type Outcome = { key: string; seq: number; statuses: unknown[] }
function latestStatuses(outcomes: Outcome[]): unknown[] {
  const latest = new Map<string, Outcome>()
  for (const o of outcomes) { const prev = latest.get(o.key); if (!prev || o.seq >= prev.seq) latest.set(o.key, o) }
  return [...latest.values()].flatMap(o => o.statuses)
}
function recordOutcomes(file: Artifact, evidence: any, events: Event[]): Outcome[] {
  const exact = (target: any) => target?.artifact_id === file.artifact_id && target?.revision === file.revision && target?.sha256 === file.sha256
  const out: Outcome[] = []
  for (const c of evidence?.checks || []) if (exact(c.target)) out.push({ key: `check:${c.kind}`, seq: c.seq, statuses: [c.status] })
  for (const c of evidence?.delivery_checks || []) if (exact(c.target)) out.push({ key: `delivery:${c.logical_path}`, seq: c.seq, statuses: [c.result?.status] })
  for (const r of evidence?.reviews || []) if ((r.target_artifacts || []).some(exact)) out.push({ key: `review:${r.target_task_id}`, seq: r.seq, statuses: (r.results || []).map((x: any) => x.status) })
  for (const e of events) {
    if (e.type === 'check.completed' && exact(e.payload.target)) out.push({ key: `check:${e.payload.kind}`, seq: e.seq, statuses: [e.payload.result?.status] })
    else if (e.type === 'delivery.checked' && exact(e.payload.target)) out.push({ key: `delivery:${e.payload.logical_path}`, seq: e.seq, statuses: [e.payload.result?.status] })
    else if (e.type === 'review.submitted' && (e.payload.target_artifacts || []).some(exact)) out.push({ key: `review:${e.payload.target_task_id}`, seq: e.seq, statuses: (e.payload.results || []).map((x: any) => x.status) })
  }
  return out
}
function checkState(file: Artifact, evidence: any, events: Event[]): CheckState {
  const statuses = latestStatuses(recordOutcomes(file, evidence, events))
  if (!statuses.length) return 'none'
  return statuses.every(s => s === 'pass') ? 'pass' : 'concern'
}
const eventTypes = ['run.created','run.started','run.queued','run.completed','run.partial','run.failed','run.cancelled','run.interrupted','run.resumed','run.blocked','team.selected','team.rejected','plan.accepted','plan.milestone','task.started','task.updated','task.ready','task.waiting','task.accepted','task.partial','task.failed','task.blocked','task.review_pending','task.cancelled','task.interrupted','artifact.published','artifact.adopted','review.submitted','check.completed','delivery.checked','approval.requested','approval.resolved','instruction.received','message.sent','model.called','model.failed','tool.called','input.read','plan.proposed','plan.rejected']

export default function Workroom({ runId, nav }: { runId: string; nav: (path: string) => void }) {
  const [run, setRun] = useState<RunDetail | null>(null)
  const [chat, setChat] = useState<ChatMessage[]>([])
  const [events,setEvents] = useState<Event[]>([])
  const [connection,setConnection] = useState('connecting')
  const [loadError, setLoadError] = useState('')
  const [actionError, setActionError] = useState('')
  const [busy, setBusy] = useState(false)
  const actionLock = useRef(false)
  const headingRef = useRef<HTMLHeadingElement>(null)
  const announced = useRef(false)
  const [goalOpen, setGoalOpen] = useState(false)
  const [panel, setPanel] = useState<JourneyPanel | null>(() => new URLSearchParams(location.search).get('view') === 'conversation' ? 'team' : requestedPanel(location.search))
  const queryTab = new URLSearchParams(location.search).get('tab')
  const [inspect, setInspect] = useState(() => ['timeline','report','chat'].includes(queryTab || ''))
  const [approvalsOpen, setApprovalsOpen] = useState(queryTab === 'approvals')
  const [paused, setPaused] = useState(false)
  const [directionDraft, setDirectionDraft] = useState('')
  const [artifactTarget,setArtifactTarget]=useState<{id:string;revision:number;sha256:string}|null>(null)
  const [teamOpenByRun,setTeamOpenByRun]=useState<Record<string,boolean>>({})
  const refreshRef = useRef<() => Promise<void>>(async () => {})
  const reconnectRef = useRef<() => Promise<void>>(async () => {})

  useEffect(() => {
    let alive = true, cursor = 0, nextConnectAt = 0
    let currentRead: AbortController | null = null
    setRun(null); setChat([]); setEvents([]); setLoadError(''); setConnection('connecting')
    let stream: EventSource | null = null
    let queued: ReturnType<typeof setTimeout> | undefined
    const refresh = async (replacePending = false) => {
      if (!alive || (currentRead && !replacePending)) return
      // Manual reload replaces an unfinished read. Poll and stream signals share one batch.
      // The deadline includes response bodies; a stalled body must not keep reload locked.
      currentRead?.abort()
      const read = new AbortController()
      currentRead = read
      const deadline = setTimeout(() => read.abort(), WORKROOM_READ_TIMEOUT_MS)
      try {
        const [detail, messages, updates] = await Promise.all([api.run(runId,read.signal), api.chat(runId,read.signal), api.events(runId,cursor,read.signal)])
        if (!alive || currentRead !== read) return
        setRun(detail); setChat(messages); setLoadError(''); if(updates.length){cursor=updates.at(-1)!.seq;setEvents(old=>[...old,...updates])} if(!streamOpen() && detail.live && !isSettled(detail.status)) connect(); else if (!streamOpen() && isSettled(detail.status)) setConnection('ended')
        return detail
      } catch { if (alive && currentRead === read) setLoadError(say('最新の状態を取得できません。表示内容が古い可能性があります。', 'Could not refresh the work. The displayed information may be out of date.')) }
      finally {
        clearTimeout(deadline)
        read.abort() // Cancel sibling GETs when one member of the batch fails.
        if (currentRead === read) currentRead = null
      }
    }
    const schedule = () => { if (!queued) queued = setTimeout(() => { queued = undefined; void refresh() }, 100) }
    // The stream is only a change signal; the fetches above carry the data. Start it after the last event
    // already loaded so a reconnect does not replay the whole history, and keep one open stream at a time.
    const streamOpen = () => !!stream && stream.readyState !== EventSource.CLOSED
    const connect = () => {
      stream?.close()
      if (!alive || Date.now() < nextConnectAt) return
      stream = new EventSource(browserApiUrl(`/api/runs/${encodeURIComponent(runId)}/stream?after_seq=${cursor}`))
      stream.onopen = () => { if(alive) setConnection('live') }
      for (const type of eventTypes) stream.addEventListener(type, schedule)
      stream.addEventListener('end', () => { stream?.close(); stream = null; setConnection('ended'); schedule() })
      stream.onerror = () => {
        if (!alive) return
        setConnection('reconnecting')
        // A network drop reconnects by itself (Last-Event-ID). A refused stream is closed: wait for the 5 s resync.
        if (stream?.readyState === EventSource.CLOSED) nextConnectAt = Date.now() + 5000
        void refresh()
      }
    }
    // A browser may drop the stream while the tab is hidden; refresh() reopens it when the run is still live.
    const foreground = () => { if (!document.hidden) void refresh() }
    // After an action (resume, cancel, adopt…) the run may start again before it is reported live; open the
    // stream for any unsettled run. The server closes it at once when nothing more will be appended.
    const ensureStream = async () => { const detail = await refresh(); if (alive && detail && !streamOpen() && !isSettled(detail.status)) connect() }
    refreshRef.current = async () => { await refresh(true) }; reconnectRef.current = ensureStream
    void ensureStream()
    // Resync after missed SSE events and external resume; only while visible.
    const timer = setInterval(() => { if (!document.hidden) void refresh() }, 5000)
    document.addEventListener('visibilitychange', foreground)
    window.addEventListener('pageshow', foreground)
    return () => { alive = false; currentRead?.abort(); stream?.close(); clearInterval(timer); clearTimeout(queued); document.removeEventListener('visibilitychange', foreground); window.removeEventListener('pageshow', foreground) }
  }, [runId])
  const refresh = useCallback(() => refreshRef.current(), [])
  const act = async (fn: () => Promise<unknown>) => {
    if (actionLock.current) return
    actionLock.current = true; setBusy(true); setActionError('')
    try { await fn(); await reconnectRef.current() }
    catch { setActionError(say('操作を完了できませんでした。状態を確認して、もう一度お試しください。', 'The action did not finish. Check the status and try again.')) }
    finally { actionLock.current = false; setBusy(false) }
  }
  const conversationOpened = useRef(false)
  useEffect(() => {
    if (!run || conversationOpened.current || new URLSearchParams(location.search).get('view') !== 'conversation') return
    conversationOpened.current = true
    const target = document.getElementById('work-conversation')
    window.scrollTo({ top: 0 })
    target?.focus({ preventScroll: true })
  }, [run])
  // Arriving from the request screen replaces the whole page; move focus to what this screen is about, once the
  // heading exists. Must stay above the early return below: hook order cannot change between renders.
  useEffect(() => { if (!announced.current && headingRef.current) { announced.current = true; headingRef.current.focus({ preventScroll: true }) } })
  if (!run) return <section className="simple-loading" aria-live="polite"><h1>{loadError ? say('この作業を読み込めませんでした。通信を確かめてから、もう一度お試しください。', 'Could not open this work. Check your connection, then try again.') : say('チームの様子を読み込んでいます…', 'Opening your work…')}</h1><button className="btn ghost" onClick={refresh}>{say('もう一度読み込む','Try again')}</button></section>
  const files = resultFiles(run.artifacts)
  const selectedPanel = panel || defaultPanel(run.status, files.length)
  const pending = run.approvals.filter(a => a.status === 'pending')
  const canWrite = run.access?.can_write !== false
  const select = (next: JourneyPanel) => {
    setPanel(next)
    // Keep both areas mounted; mobile switches visibility without discarding drafts.
    const calm = paused || window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    const target = document.getElementById(next === 'team' ? 'work-conversation' : `room-${next}`)
    requestAnimationFrame(()=>{target?.scrollIntoView({ block: 'start', behavior: calm ? 'auto' : 'smooth' });target?.focus({ preventScroll: true })})
    const url = new URL(location.href); url.searchParams.set('view', next); url.searchParams.delete('tab')
    history.replaceState(history.state, '', url.pathname + url.search + url.hash)
  }
  const prepareDirection=(text:string)=>{
    setDirectionDraft(old=>old.trim()?`${old}\n\n${text}`:text)
    select('team')
    requestAnimationFrame(()=>{const section=document.querySelector<HTMLDetailsElement>('.conversation-direction');if(section)section.open=true;document.getElementById('team-direction')?.focus()})
  }
  const reviewNotes: string[] = [...new Set(run.tasks.flatMap(t => [t.blocked_reason, ...(t.result?.unverified || [])]).filter((v): v is string => !!v))]
  const interpretationNotes = [...new Set<string>((run.final_report?.narrative?.unresolved || []).filter((note: string) => !!note))]
  // A review of another version is not evidence for this file.
  const evidence = run.final_report?.evidence
  const latestFiles = [...new Map(files.map(f => [f.artifact_id, f] as const).sort((a, b) => a[1].revision - b[1].revision)).values()]
  const uncheckedFiles = latestFiles.filter(f => checkState(f, evidence, events) === 'none').length
  const flaggedFiles = latestFiles.filter(f => checkState(f, evidence, events) === 'concern').length
  // What the coordinator says must follow the adoption that already happened, not keep asking for it.
  const adoptedList = Object.entries(run.artifact_selection || {})
  const unselectedFiles = latestFiles.filter(f => !run.artifact_selection?.[f.artifact_id]).length
  const adoptedUnverified = adoptedList.filter(([artifactId, selection]) => {
    const file = run.artifacts.find(a => a.artifact_id === artifactId && a.revision === selection.revision)
    return !file || checkState(file, evidence, events) !== 'pass'
  }).length
  // Who owns which task, so that "t2" in a model's own words can be shown as that teammate's work.
  const owners: Record<string,string> = Object.fromEntries(run.tasks.map(t => { const a = run.config_snapshot?.agents?.[t.spec.owner]; return [t.spec.id, a?.display_name || botName(a?.role || t.spec.owner, getLang())] }))
  const runnable = ['created','queued','planning','running'].includes(run.status)
  const teammates = teamOrder(Object.entries(run.config_snapshot?.agents || {}).filter(([,a]) => a.enabled && (run.inputs.team_selection !== 'adaptive' || !!run.config_snapshot?.team_recommendation || a.role === 'master')))
  const compactTeam = isSettled(run.status) && files.length > 0 && selectedPanel === 'results' && pending.length === 0
  // Runtime wording stays available on hover and in the detailed record; the everyday view says it plainly.
  const noteCount = (run.blocked_reason ? 1 : 0) + reviewNotes.length + interpretationNotes.length
  const notices = noteCount > 0 ? <details className="room-notes">
    <summary>{say('確認事項','Needs attention')}（{noteCount}）</summary>
    {(run.blocked_reason || reviewNotes.length > 0) && <ul>
      {run.blocked_reason && <li title={run.blocked_reason}><b>{say('止まった理由','Why work stopped')}</b> {friendlyReason(run.blocked_reason, getLang())}</li>}
      {reviewNotes.map((note, i) => <li key={i} title={note}>{friendlyReason(note, getLang())}</li>)}
    </ul>}
    {interpretationNotes.length > 0 && <>
      <h3>{say('AIによる解釈（確認が必要）', 'AI interpretation (needs confirmation)')}</h3>
      <ul>{interpretationNotes.map((note, i) => <li key={i}>{note}</li>)}</ul>
    </>}
  </details> : null
  return <div data-studio-panel={selectedPanel} className={`simple-workroom creation-studio desk-workroom ${files.length?'has-results':'no-results'}${paused ? ' motion-paused' : ''}`}>
    <Link to={`/runs?filter=${workFilter(new URLSearchParams(location.search).get('from'))}`} nav={nav} className="work-back">{say('← 作業一覧に戻る','← Back to work')}</Link>
    {run.provider_kind === 'fake' && <p className="demo-notice">{say('テスト表示です。実際のAIによる作業ではありません。','Test display. This is not work performed by a real AI.')}</p>}
    <section className={`work-status room-head tone-${pending.length ? 'attention' : stateTone(run.status)}`} aria-label={say('進み具合','Progress')}>
<div className="status-voice">{(() => { const m = Object.entries(run.config_snapshot?.agents || {}).find(([, a]) => a.enabled && a.role === 'master'); return m ? <BotAvatar id={m[0]} role={m[1].role} emoji={m[1].emoji} name={m[1].display_name || botName(m[1].role, getLang())} state={(() => { const mine = run.tasks.filter(t => t.spec.owner === m[0]); const raw = botActivity(mine, run.status, m[0], m[1].role, true); return coordinatorPlanned(m[1].role, mine.length, !!run.plan, raw, run.status) ? 'done' : raw })()} /> : null })()}      <div role="status"><strong>{pending.length ? say('あなたの確認が必要です','Your approval is needed') : statusLabel(run.status, getLang())}</strong><p>{run.status !== 'completed' ? null
        : adoptedList.length > 0 ? (adoptedUnverified > 0
          ? say(`使う版を${adoptedList.length}件選びました。そのうち${adoptedUnverified}件は、確認を通過した記録がないまま採用しています。`, adoptedUnverified === 1 ? `${adoptedList.length} version(s) chosen. 1 was chosen without a passing check record.` : `${adoptedList.length} versions chosen. ${adoptedUnverified} were chosen without a passing check record.`)
          : say(`使う版を${adoptedList.length}件選びました。${unselectedFiles ? `残り${unselectedFiles}件も記録を見てから選べます。` : ''}`, `${adoptedList.length} ${adoptedList.length===1?'version':'versions'} chosen.${unselectedFiles ? ` Review the ${unselectedFiles} remaining ${unselectedFiles===1?'file':'files'} before choosing.` : ''}`))
        : flaggedFiles > 0 ? say(`要修正・未確認の項目が記録されたファイルが${flaggedFiles}件あります。記録を見てから、使う版を選んでください。`,`${flaggedFiles} file(s) have checks that failed or were left unverified. Read the record before choosing a version.`)
        : uncheckedFiles > 0 ? say(`確認の記録がないファイルが${uncheckedFiles}件あります。中身と記録を見てから、使う版を選んでください。`,`${uncheckedFiles} file(s) have no check record. Read them and the record before choosing a version.`)
        : say('成果物と確認内容を見てから、使う版を選べます。','Review the files and checks, then choose a version to use.')}</p></div></div>
      <div className="work-actions"><span className="cost-summary">{say('使用額','Used')} {money(run.usage.cost_usd)}{run.usage.reserved_usd > 0 ? ` · ${say('処理中の確保額','Reserved')} ${money(run.usage.reserved_usd)}` : ''}</span>
        {canWrite && runnable && <button className="btn ghost" disabled={busy} onClick={() => act(() => api.cancel(runId))}>{say('作業を止める','Stop work')}</button>}
        {canWrite && run.plan && ['interrupted','partial','failed','cancelled'].includes(run.status) && <details className="desk-resume" onToggle={e => {
          if (!e.currentTarget.open) return
          const panel = e.currentTarget.querySelector<HTMLElement>(':scope > div')
          // Opening the warning must also reveal its confirmation at browser zoom.
          if (panel && panel.getBoundingClientRect().bottom > window.innerHeight - 16) panel.scrollIntoView({ block: 'end', behavior: 'instant' })
        }}><summary className="btn signal">{say('続きを進める','Continue work')}</summary><div><p>{say('途中の作業を再実行する場合があります。送信済みの資料・外部処理は取り消されません。','Unfinished tasks may run again. Sent material and completed external effects cannot be undone.')}</p><button className="btn signal" disabled={busy} onClick={() => act(() => api.resume(runId))}>{say('確認して再開','Confirm and continue')}</button></div></details>}
        <button className="btn ghost" onClick={() => nav('/')}>{say('新しくお願いする','New request')}</button>
      </div>
      <header className="simple-run-heading room-goal">

        <h1 ref={headingRef} tabIndex={-1} className={goalOpen ? undefined : 'goal-clamp'} title={goalOpen ? undefined : run.goal}>{run.goal}</h1>
        {run.goal.length > 70 && <button type="button" className="goal-toggle" aria-expanded={goalOpen} onClick={() => setGoalOpen(!goalOpen)}>{goalOpen ? say('たたむ','Collapse') : say('全文を表示','Show all')}</button>}
      </header>
    </section>
    {loadError && <p className="work-warning" role="alert">{loadError} <button className="btn ghost" onClick={refresh}>{say('再読み込み','Refresh')}</button></p>}
    {actionError && <p className="work-warning" role="alert">{actionError}</p>}
    {pending.length > 0 && <section className="approval-callout" aria-label={say('あなたの確認が必要です','Your approval is needed')}>
      <div><strong>{say('あなたの確認が必要です','Your approval is needed')} · {pending.length}{say('件',' item(s)')}</strong><p>{say('内容を確認してから選んでください。自動では承認しません。','Read the proposed action before deciding. Nothing is automatically approved.')}</p></div>
      <button className="btn signal" aria-expanded={approvalsOpen} aria-controls="simple-approvals" onClick={() => setApprovalsOpen(!approvalsOpen)}>{approvalsOpen ? say('閉じる','Close') : say('内容を確認','Review action')}</button>
      {approvalsOpen && <div id="simple-approvals"><ApprovalCards approvals={pending} readOnly={!canWrite} refresh={refresh} /></div>}
    </section>}
    <nav className="room-view-nav" aria-label={say('作業の表示', 'Work views')}>
      <button type="button" aria-current={selectedPanel === 'team' ? 'location' : undefined} onClick={() => select('team')}>{say('会話', 'Conversation')}</button>
      <button type="button" aria-current={selectedPanel === 'results' ? 'location' : undefined} onClick={() => select('results')}>{say('成果物', 'Results')} <span>{latestFiles.length}</span></button>
    </nav>
    <div className="room-grid room-live-grid">
      <div className="room-side">
        {notices}
        {run.config_snapshot?.team_recommendation && <details className="team-recommendation"><summary>{say('今回のチーム構成','This task’s team')}</summary><p>{run.config_snapshot.team_recommendation.reason}</p><ul>{run.config_snapshot.team_recommendation.members.map((m,i)=><li key={i}><strong>{m.name} · {m.specialty}</strong><p>{m.reason}</p></li>)}</ul></details>}
        <section id="room-team" className={`simple-team-room room-team${compactTeam?' is-compact':''}`} aria-label={say('チームの様子','Your team')}>
      <details className="team-disclosure" open={!compactTeam || !!teamOpenByRun[runId]}>
        <summary hidden={!compactTeam} onFocus={e=>{
          // Native focus can leave a partly visible label behind the narrow-screen sticky menu.
          const menu=document.querySelector('.top.side')?.getBoundingClientRect(), target=e.currentTarget.getBoundingClientRect()
          if(menu && menu.right>target.left && menu.left<target.right && target.top<menu.bottom+8 && target.bottom>menu.top)
            window.scrollBy({top:target.top-menu.bottom-8,behavior:'instant'})
        }} onClick={e=>{e.preventDefault();if(compactTeam)setTeamOpenByRun(old=>({...old,[runId]:!old[runId]}))}}><span>{say('AIチーム','AI team')} · {teammates.length}{say('名',' members')}</span><span className="team-disclosure-hint">{say('担当と作業を見る','Roles & work')}</span></summary>
      <div className="team-expanded"><div className="team-section-heading"><h2>{say('AIチーム','AI team')}</h2><button type="button" className="btn ghost" aria-pressed={paused} onClick={()=>setPaused(!paused)}>{paused?say('動きを再開','Resume animation'):say('動きを止める','Pause animation')}</button></div><ol className="team-stage">{teammates.map(([id,a]) => {
        const tasks = run.tasks.filter(t => t.spec.owner === id), raw = botActivity(tasks, run.status, id, a.role, a.enabled)
        const state = coordinatorPlanned(a.role, tasks.length, !!run.plan, raw, run.status) ? 'done' : raw
        const task = tasks.find(t => t.status === 'running') || tasks.find(t => !['accepted','cancelled'].includes(t.status)) || tasks[tasks.length - 1]
        const active = ['thinking','researching','building','reviewing'].includes(state)
        return <li className={`desk-teammate state-${state}${active ? ' is-active' : ''}`} key={id}>
          <details><summary><BotAvatar id={id} role={a.role} name={a.display_name || botName(a.role,getLang())} emoji={a.emoji} state={state} size="micro" /><span>{a.display_name || botName(a.role,getLang())}</span><span className="desk-bot-state">{botStateLabel(state,getLang())}</span></summary>
          <div className="desk-person-detail"><strong>AI · {a.specialty || roleLabel(a.role,getLang())} · {botStateLabel(state,getLang())}</strong><p>{task?friendlyWorkText(task.spec.objective, owners, getLang()):say('担当する作業はまだありません。','No task assigned yet.')}</p></div></details>
        </li>
      })}</ol>
      {Object.keys(run.config_snapshot?.agents || {}).length === 0 && <p className="simple-empty">{say('チームの準備ができると、ここに仲間が表示されます。','Your teammates appear here once the team is ready.')}</p>}
      </div></details>
        </section>
        <div id="room-request"><details className="simple-request pane" aria-label={say("お願いの内容","Your request")}><summary>{say('資料と前提','Materials & context')}</summary>
      {!run.inputs.text && run.inputs.files.length === 0 && run.inputs.urls.length === 0 && <p className="simple-empty">{say('資料や参照先は添えられていません。','No files or references were attached.')}</p>}
      {run.inputs.text && <details className="request-text"><summary>{say('添えた文章を見る','Show the attached text')}</summary><pre>{run.inputs.text}</pre></details>}{run.inputs.files.length > 0 && <p>{say('渡した資料','Attached files')}: {run.inputs.files.map(f => f.name).join(' / ')}</p>}
      {run.inputs.urls.length > 0 && <p className="request-urls">{say('参照先','References')}: {run.inputs.urls.join(' / ')}</p>}
      {!!run.plan?.assumptions.length && <div><h3>{say('進めるうえでの前提','Working assumptions')}</h3><ul>{run.plan.assumptions.map((a, i) => <li key={i}>{a}</li>)}</ul></div>}
    </details></div>

      </div>
      <div className="room-main">
      <div id="work-conversation" tabIndex={-1}><TeamConversation key={runId} run={run} chat={chat} events={events} onOpenArtifact={ref=>{setArtifactTarget({id:ref.artifact_id,revision:ref.revision,sha256:ref.sha256});select('results')}} connection={loadError ? 'reconnecting' : connection}><Direction run={run} refresh={refresh} text={directionDraft} setText={setDirectionDraft} onNewRequest={carried => { const d = readRequestDraft(); saveRequestDraft({ ...d, goal: d.goal.trim() ? `${d.goal}\n\n${carried}` : carried }); nav('/') }} /></TeamConversation></div>
      <div id="room-results" tabIndex={-1}><section className="simple-results" aria-label={say('できたもの','Your results')}>
      {files.length > 0 && run.status !== 'completed' && <p className="work-warning">{isSettled(run.status) ? say('依頼全体は完了していません。使える途中成果を確認できます。','The request is not complete. These are the available partial results.') : say('作業途中の内容です。確認・修正で変わることがあります。','These are drafts. They may change as the team checks and revises them.')}</p>}
      <Deliverables key={runId} run={run} events={events} refresh={refresh} target={artifactTarget} clearTarget={()=>setArtifactTarget(null)} onDirection={prepareDirection} />
    </section></div></div>
    </div>
    <details className="work-progress-disclosure"><summary>{say('進行状況','Progress')}</summary><button type="button" className="btn ghost" aria-pressed={paused} onClick={()=>setPaused(!paused)}>{paused?say('動きを再開','Resume animation'):say('動きを止める','Pause animation')}</button><WorkProgress run={run} events={events} /></details>
    <details id="run-inspector" className="work-inspector" open={inspect} onToggle={e => setInspect(e.currentTarget.open)}>
      <summary>{say('詳しい作業記録・設定','Detailed work record & controls')}</summary>
      {inspect && <Suspense fallback={<p>{say('詳細を読み込んでいます…','Loading details…')}</p>}><Inspector runId={runId} nav={nav} /></Suspense>}
    </details>
  </div>
}

function Direction({ run, refresh, text, setText, onNewRequest }: { run: RunDetail; refresh: () => Promise<void>; text: string; setText: (value: string) => void; onNewRequest: (text: string) => void }) {
  const [busy,setBusy] = useState(false), [note,setNote] = useState(''), [error,setError] = useState('')
  const lock = useRef(false)
  const allowed = run.access?.can_instruct ?? (run.access?.can_write !== false && ['created','queued','planning','running'].includes(run.status))
  const paused = ['interrupted','partial','failed','cancelled','approval_required'].includes(run.status)
  const send = async (e: FormEvent) => {
    e.preventDefault(); if (lock.current || !allowed || !text.trim() || text.length>4000) return
    lock.current = true; setBusy(true); setError(''); setNote('')
    try { await api.instruction(run.run_id,{text:text.trim(),kind:'change'}); setText(''); setNote(paused ? say('指示を保存しました。作業は停止したままです。','Direction saved. Work remains paused.') : say('受け取りました。次に始まる作業へ渡します。','Received. This will be passed to the next task.')); await refresh() }
    catch { setError(say('送れませんでした。入力は残してあります。','Could not send. Your text has been kept.')) }
    finally { lock.current=false;setBusy(false) }
  }
  // A finished run cannot take directions. Do not show a dead, disabled form: offer the one thing that works,
  // a new request that carries the text (for example a "request a change" note prepared from a result).
  if (!allowed) return <div className="simple-direction is-closed">
    {run.latest_instruction && <details className="saved-direction"><summary>{say('最後に保存した指示を見る','View the last saved direction')}</summary><p>{String(run.latest_instruction.payload.text)}</p><small>{say('保存の記録です。適用や修正の完了を示すものではありません。','This records receipt, not application or completion.')}</small></details>}
    <p id="direction-note">{run.access?.can_write === false ? say('閲覧権限では指示を送れません。','Read-only access cannot send directions.') : say('この作業には、もう指示を送れません。直したい点は新しいお願いにできます。','This work no longer takes directions. You can make the change a new request.')}</p>
    {text.trim() && <p className="direction-carry">{text}</p>}
    {run.access?.can_write !== false && <button type="button" className="btn ghost" onClick={() => onNewRequest(text.trim())}>{text.trim() ? say('この内容で新しくお願いする','Start a new request with this text') : say('新しくお願いする','New request')}</button>}
  </div>
  return <form className="simple-direction" onSubmit={send}>
    {run.latest_instruction && <details className="saved-direction"><summary>{say('最後に保存した指示を見る','View the last saved direction')}</summary><p>{String(run.latest_instruction.payload.text)}</p><small>{say('保存の記録です。適用や修正の完了を示すものではありません。','This records receipt, not application or completion.')}</small></details>}
    <label htmlFor="team-direction">{say('チームに伝える','Tell your team')}</label>
    <p id="direction-note">{allowed && paused ? say('修正指示を先に保存できます。再開後、次に始まる作業へ渡します。完了した作業や計画は自動でやり直しません。','Save a correction before continuing. It reaches the next task session after resume; completed tasks and the plan are not automatically redone.') : allowed ? say('次に始まる作業へ渡します。今の計画は自動では書き換えません。','Passed to the next task. The current plan is not automatically rewritten.') : say('この状態または権限では指示を保存できません。必要なら新しい依頼を作成してください。','This state or permission does not allow directions. Create a new request if needed.')}</p>
    <textarea id="team-direction" className="input" aria-describedby="direction-note" placeholder={say('例：もっと短く、やさしい文章にして','For example: make it shorter and easier to read')} value={text} onChange={e=>setText(e.target.value)} maxLength={4000} disabled={!allowed || busy} />
    {text.length>4000&&<p role="alert">{say('指示が4000文字を超えています。内容を短くしてから送信してください。','Shorten the direction to 4,000 characters before sending.')}</p>}
    <div className="direction-footer"><span role="status">{note}</span><button className="btn signal" type="submit" disabled={!allowed || busy || !text.trim() || text.length>4000}>{busy?say('送っています…','Sending…'):paused?say('修正指示を保存','Save correction'):say('伝える','Send')}</button></div>
    {error && <p role="alert">{error}</p>}
  </form>
}

function ApprovalCards({ approvals,readOnly,refresh }: { approvals: Approval[]; readOnly: boolean; refresh: () => Promise<void> }) {
  const [busy,setBusy] = useState(false), [error,setError]=useState(''); const lock=useRef(false)
  const resolve = async (a: Approval, decision: 'approve'|'reject') => {
    if(readOnly || lock.current)return;lock.current=true;setBusy(true);setError('')
    try{await api.resolveApproval(a.approval_id,{decision,expected_hash:a.payload_hash,nonce:a.nonce});await refresh()}
    catch{setError(say('確認を保存できません。内容が変わっていないか、再読み込みしてください。','Could not save the decision. Refresh to check whether the action has changed.'))}
    finally{lock.current=false;setBusy(false)}
  }
  return <>{error&&<p role="alert">{error}</p>}{approvals.map(a=><article className="simple-approval" key={a.approval_id}>
    <h3>{String(a.payload.description||a.action)}</h3><p>{say('実行する操作','Action')}: {a.action}</p>
    <ApprovalDetails value={a.payload.payload ?? a.payload} /><p>{say('有効期限','Expires')}: {fmtTime(a.expires_at)}{a.payload.estimated_cost_usd!=null ? ` · ${say('見積もり','Estimate')} $${a.payload.estimated_cost_usd}`:''}</p>
    {readOnly?<p>{say('閲覧権限では承認できません。','Read-only access cannot approve this action.')}</p>:<div className="row"><button className="btn signal" disabled={busy} onClick={()=>resolve(a,'approve')}>{say('この内容で承認','Approve this action')}</button><button className="btn ghost" disabled={busy} onClick={()=>resolve(a,'reject')}>{say('承認しない','Decline')}</button></div>}
  </article>)}</>
}

// What will be done must stay fully visible before approval, but as labelled lines rather than a JSON dump.
// Only nested values keep their exact source text, inside a disclosure.
function ApprovalDetails({ value }: { value: unknown }) {
  const entries = value && typeof value === 'object' && !Array.isArray(value) ? Object.entries(value as Record<string, unknown>) : []
  if (!entries.length) return value == null || (typeof value === 'object' && !Array.isArray(value)) ? null : <p className="approval-value">{String(value)}</p>
  return <dl className="approval-details">{entries.map(([key, v]) => <div key={key}><dt>{key}</dt><dd>{v !== null && typeof v === 'object'
    ? <details><summary>{say('内容を表示','Show contents')}</summary><pre>{JSON.stringify(v, null, 2)}</pre></details>
    : String(v)}</dd></div>)}</dl>
}

type ArtifactDetail = Artifact & { text?: string; checks: Event[]; reviews: Event[] }
function Deliverables({run,events,refresh,target,clearTarget,onDirection}:{run:RunDetail;events:Event[];refresh:()=>Promise<void>;target:{id:string;revision:number;sha256:string}|null;clearTarget:()=>void;onDirection:(text:string)=>void}) {
  const [showSource,setShowSource]=useState(false)
  const [readAttempt,setReadAttempt]=useState(0)
  const [recordOpen,setRecordOpen]=useState(false)
  const shown=useRef(''), focusChoice=useRef(false), choiceRef=useRef<HTMLSpanElement>(null), recordRef=useRef<HTMLElement>(null), readRetryRef=useRef<HTMLButtonElement>(null)
  // Use the same exact revision/hash rule as the status line.
  const evidence=run.final_report?.evidence
  const latestState=new Map<string,CheckState>(resultFiles(run.artifacts).filter((f,_,all)=>f.revision===Math.max(...all.filter(x=>x.artifact_id===f.artifact_id).map(x=>x.revision))).map(f=>[f.artifact_id,checkState(f,evidence,events)]))
  const versions = new Map<string,Artifact[]>()
  for(const file of resultFiles(run.artifacts)){const list=versions.get(file.artifact_id)||[];list.push(file);versions.set(file.artifact_id,list)}
  for(const list of versions.values())list.sort((a,b)=>a.revision-b.revision)
  const [selection,setSelection]=useState<{id:string;revision:number}|null>(null)
  useEffect(()=>{if(target)setSelection({id:target.id,revision:target.revision})},[target])
  const keys=[...versions.keys()]
  const first=(keys.find(k=>versions.get(k)!.some(f=>f.media_type.includes('html')))||keys[keys.length-1]) as string|undefined
  const id=selection?selection.id:first
  const list=id?versions.get(id)||[]:[]
  const adopted=id?run.artifact_selection?.[id]:undefined
  const revision=selection&&selection.id===id?selection.revision:adopted?.revision
  const file=revision!=null?list.find(a=>a.revision===revision):list[list.length-1]
  useEffect(()=>{if(file&&!selection)setSelection({id:file.artifact_id,revision:file.revision})},[file,selection])
  const [loadedDetail,setDetail]=useState<ArtifactDetail|null>(null),[error,setError]=useState(''),[note,setNote]=useState(''),[busy,setBusy]=useState(false)
  const [read,setRead]=useState<{key:string;state:'pending'|'ready'|'error';message:string}>({key:'',state:'pending',message:''})
  const fileId=file?.artifact_id, fileRevision=file?.revision, fileSha=file?.sha256
  const readKey=fileId?JSON.stringify([run.run_id,fileId,fileRevision,fileSha]):''
  // A previous response may remain mounted for the same bytes, never for another run or revision.
  const detail=loadedDetail&&file&&loadedDetail.run_id===run.run_id&&loadedDetail.artifact_id===file.artifact_id&&loadedDetail.revision===file.revision&&loadedDetail.sha256===file.sha256?loadedDetail:null
  const readState=read.key===readKey?read.state:'pending'
  const readReady=readState==='ready'&&!!detail
  const lock=useRef(false)
  useEffect(()=>{
    if(!fileId||fileRevision==null||!fileSha)return
    let alive=true, timedOut=false
    const controller=new AbortController()
    if(shown.current!==readKey){shown.current=readKey;setDetail(null);setNote('')}
    setError('');setRead({key:readKey,state:'pending',message:''})
    const deadline=setTimeout(()=>{timedOut=true;controller.abort()},ARTIFACT_READ_TIMEOUT_MS)
    api.artifact(run.run_id,fileId,fileRevision,controller.signal).then(d=>{
      if(!alive||controller.signal.aborted)return
      if(d.run_id!==run.run_id||d.artifact_id!==fileId||d.revision!==fileRevision||d.sha256!==fileSha)throw new Error('Artifact version mismatch')
      setDetail(d);setRead({key:readKey,state:'ready',message:''})
    }).catch(()=>{
      if(alive)setRead({key:readKey,state:'error',message:timedOut
        ?say('本文と確認の記録の取得に時間がかかっています。再読み込みして確認してください。','Loading the file and check record is taking too long. Reload them to try again.')
        :say('本文と確認の記録を取得できませんでした。再読み込みして確認してください。','Could not retrieve the file and check record. Reload them to try again.')})
    }).finally(()=>clearTimeout(deadline))
    return()=>{alive=false;clearTimeout(deadline);controller.abort()}
  },[run.run_id,fileId,fileRevision,fileSha,readKey,run.last_seq,readAttempt])
  useEffect(()=>{
    if(!readReady)return
    const frame=requestAnimationFrame(()=>{
      const button=readRetryRef.current
      if(!button||document.activeElement!==button)return
      // Loaded text can push this still-focused control below the viewport. Keep its position visible without moving focus.
      const rect=button.getBoundingClientRect(), menu=document.querySelector('.top.side')?.getBoundingClientRect()
      const top=menu&&menu.right>rect.left&&menu.left<rect.right?Math.max(8,menu.bottom+8):8
      if(rect.top<top||rect.bottom>window.innerHeight-8)button.scrollIntoView({block:'center',behavior:'instant'})
    })
    return()=>cancelAnimationFrame(frame)
  },[readReady,readKey])
  useEffect(()=>{if(focusChoice.current&&adopted?.revision===file?.revision){focusChoice.current=false;choiceRef.current?.focus()}},[adopted?.revision,file?.revision])
  if((selection&&!file)||(target&&file?.artifact_id===target.id&&file.revision===target.revision&&file.sha256!==target.sha256))return <p role="alert">{say('参照された版を確認できません。','The referenced version could not be verified.')} <button className="btn ghost" onClick={()=>{clearTarget();setSelection(null)}}>{say('成果物一覧へ','Back to results')}</button></p>
  if(!file)return <div className="result-empty pane"><span aria-hidden="true">📄</span><h2>{isSettled(run.status) ? say('保存できる成果物はありません','No files are available to save') : say('成果物ができると、ここに届きます','Your files will appear here')}</h2><p>{isSettled(run.status) ? say('公開された成果物がない状態で、この依頼は終了または停止しています。状態と作業記録を確認してください。','This request ended or stopped without a published result. Check its status and work record.') : say('進み具合とチームのやり取りを確認しながらお待ちください。公開された版と確認の記録を、ここで読んで保存できます。','Follow progress and the team conversation while work continues. Published files and their check records can be read and saved here.')}</p></div>
  const exact=(target:any)=>target?.artifact_id===file.artifact_id&&target?.revision===file.revision&&target?.sha256===file.sha256
  const checks=(detail?.checks||[]).filter(e=>exact(e.payload.target))
  const reviews=(detail?.reviews||[]).filter(e=>(e.payload.target_artifacts||[]).some(exact))
  const reviewAuthor=(event:Event)=>{const agent=run.config_snapshot?.agents?.[event.actor_id];return agent?.display_name || (agent?botName(agent.role,getLang()):event.actor_id || say('確認者','Reviewer'))}
  const outcomes=latestStatuses([...checks.map(e=>({key:e.type==='delivery.checked'?`delivery:${e.payload.logical_path}`:`check:${e.payload.kind}`,seq:e.seq,statuses:[e.payload.result?.status]})),...reviews.map(e=>({key:`review:${e.payload.target_task_id}`,seq:e.seq,statuses:(e.payload.results||[]).map((r:any)=>r.status)}))])
  const pass=outcomes.length>0&&outcomes.every(s=>s==='pass'), concern=outcomes.some(s=>s!=='pass')
  // While the record is loading, say so; "no record" would be a claim the page has not checked yet.
  const loadingRecord=readState==='pending'
  const unavailableRecord=readState==='error'
  const recordMessage=loadingRecord?say('確認の記録を読み込んでいます…','Loading the check record…'):say('確認の記録を取得できません。再読み込みしてください。','The check record is unavailable. Please reload it.')
  const isMarkdown=/markdown/.test(file.media_type)||/\.(md|markdown)$/i.test(file.logical_path)
  // The adopt button disappears once pressed; hand focus to what replaced it so keyboard users are not dropped on <body>.
  const useVersion=async()=>{if(lock.current||!readReady)return;lock.current=true;setBusy(true);setNote('');try{await api.adoptArtifact(run.run_id,file.artifact_id,{revision:file.revision,expected_selected_revision:adopted?.revision ?? 0});setNote(say('この版を使うことにしました。','This version is now selected.'));focusChoice.current=true;await refresh()}catch{setError(say('選択を保存できませんでした。再読み込みしてお試しください。','Could not save your choice. Refresh and try again.'))}finally{lock.current=false;setBusy(false)}}
  const selectedCount=Object.keys(run.artifact_selection || {}).length
  const openRecord=()=>{setRecordOpen(true);requestAnimationFrame(()=>{recordRef.current?.focus();recordRef.current?.scrollIntoView({block:'center'})})}
  return <section className="pane simple-deliverables result-workflow" data-artifact-read-state={readState}>
    {versions.size>1&&<div className="result-file-list" aria-label={say('ファイルを選ぶ','Choose a file')}>{[...versions.entries()].map(([key,items])=><button className={key===id?'active':''} type="button" aria-pressed={key===id} key={key} onClick={()=>{clearTarget();setSelection({id:key,revision:run.artifact_selection?.[key]?.revision||items[items.length-1].revision})}}><span aria-hidden="true">📄</span>{items[items.length-1].logical_path}{run.artifact_selection?.[key]&&<span className="tab-chosen" title={say('あなたが選んだ版があります','You selected a version')}>{say('採用','Chosen')}</span>}{latestState.get(key)==='none'&&<span className="tab-mark" role="img" aria-label={say('確認の記録なし','No check record')} title={say('確認の記録なし','No check record')}>?</span>}{latestState.get(key)==='concern'&&<span className="tab-mark is-concern" role="img" aria-label={say('要修正・未確認の項目あり','Failed or unverified items')} title={say('要修正・未確認の項目あり','Failed or unverified items')}>!</span>}</button>)}</div>}
    <div className="result-reading-head">
      <div className="result-file-identity"><span className="result-step">{say('01 読む','01 Read')}</span><h2>{file.logical_path}</h2><p>{say('版','Version')} {file.revision} · {adopted?.revision===file.revision?say('採用した版','Selected version'):say('未採用の候補','Unselected candidate')}</p></div>
      {list.length>1&&<label className="result-version-picker">{say('表示する版','Version to read')}<select value={file.revision} onChange={e=>{clearTarget();setSelection({id:file.artifact_id,revision:Number(e.target.value)})}}>{list.map(f=><option key={f.revision} value={f.revision}>{say('版','Version')} {f.revision}{adopted?.revision===f.revision?say('（採用）',' (selected)'):''}</option>)}</select></label>}
      <div className="result-display-tools">{isMarkdown&&<button type="button" className="btn ghost" aria-pressed={showSource} onClick={()=>setShowSource(!showSource)}>{showSource?say('読みやすく表示','Show formatted'):say('原文を表示','Show source')}</button>}<a className="btn ghost" href={api.artifactRawUrl(run.run_id,file.artifact_id,file.revision)} target="_blank" rel="noreferrer">{say('別のタブで開く','Open in a new tab')} <span aria-hidden="true">↗</span></a></div>
    </div>
    {error&&<p className="work-warning" role="alert">{error} <button className="btn ghost" onClick={()=>setReadAttempt(n=>n+1)}>{say('再読み込み','Refresh')}</button></p>}
    {unavailableRecord&&<p className="work-warning" role="alert">{read.message}{detail&&<> {say('前回取得した本文を表示しています。','The previously retrieved file is still shown.')}</>}</p>}
    <div id="result-body" className="result-reader" role="region" aria-label={say(`成果物：${file.logical_path}`,`Result: ${file.logical_path}`)} tabIndex={0}>{file.media_type.includes('html')?<iframe title={file.logical_path} sandbox="" src={api.artifactRawUrl(run.run_id,file.artifact_id,file.revision)}/>:isMarkdown&&detail?.text!=null&&!showSource?<Markdown text={detail.text} className="md result-md"/>:<pre>{detail?.text ?? (detail?say('この形式は別のウィンドウで開いてください。','Open this file in a new window to view it.'):unavailableRecord?say('本文をまだ表示できません。下の再読み込みで確認できます。','The file is unavailable. Use reload below to try again.'):say('読み込み中…','Loading…'))}</pre>}</div>
    <section className="result-checks" aria-labelledby="result-checks-title">
      <h3 id="result-checks-title" className="result-step">{say('02 確認の記録を読む','02 Read the check record')}</h3>
      <div className={`result-review-summary is-${loadingRecord?'loading':unavailableRecord?'none':pass?'pass':concern?'concern':'none'}`}>
        <span id="artifact-read-status" className="review-state" role="status"><b aria-hidden="true">{loadingRecord?'…':unavailableRecord?'?':pass?'✓':concern?'!':'?'}</b>{loadingRecord||unavailableRecord?recordMessage:pass?say('この版の記録された確認は通過','Recorded checks passed for this version'):concern?say('この版には未確認・要修正の項目があります','This version has unchecked or flagged items'):say('未確認：この版の確認記録はまだありません','Unverified: No check record for this version yet')}</span>
        <button type="button" className="review-link" aria-controls="result-record" onClick={openRecord}>{say('確認の記録を見る','See the check record')}</button>
        <button type="button" className="review-link" ref={readRetryRef} data-artifact-retry aria-controls="result-body result-record" aria-describedby="artifact-read-status" onClick={()=>setReadAttempt(n=>n+1)}>{say('本文と確認を再読み込み','Reload file and checks')}</button>
      </div>
      <p className="result-check-limit">{say('確認は表示中の版に対する記録です。内容の完全な正しさを保証するものではありません。','These checks apply to the version shown. They do not guarantee that every statement is correct.')}</p>
    <details id="result-record" className="result-record" open={recordOpen} onToggle={e=>setRecordOpen(e.currentTarget.open)}><summary ref={recordRef}>{say('版と確認の記録','Versions & check record')}</summary>
      <p>{file.logical_path} · {say('版','Version')} {file.revision} · <span title={file.sha256}>{say('この版の識別子','Version identifier')} <code>{file.sha256.slice(0,12)}</code></span></p>
      <ul className="check-record">
        {readReady&&checks.map(e=><li key={e.event_id}><span className={`check-mark is-${e.payload.result?.status||'unknown'}`}>{outcomeLabel(e.payload.result?.status,getLang())}</span>{e.type==='delivery.checked'?say('依頼した必須条件','Required delivery conditions'):say('自動チェック','Automatic check')} <code>{String(e.payload.kind||e.payload.result?.kind||'')}</code>{e.payload.result?.problems?.length?<span className="check-detail"> — {e.payload.result.problems.join(' / ')}</span>:null}{e.payload.result?.detail?<span className="check-detail"> — {String(e.payload.result.detail).slice(0,240)}</span>:null}</li>)}
        {readReady&&reviews.flatMap(e=>(e.payload.results||[]).map((r:any,n:number)=><li key={e.event_id+n}><span className={`check-mark is-${r.status}`}>{outcomeLabel(r.status,getLang())}</span>{say(`${reviewAuthor(e)}の確認`,`Review by ${reviewAuthor(e)}`)} <code>{String(r.acceptance_id||'')}</code>{r.evidence||r.reason?<span className="check-detail"> — {String(r.evidence||r.reason).slice(0,240)}</span>:null}</li>))}
        {!readReady&&<li className="is-quiet">{recordMessage}</li>}
        {readReady&&checks.length+reviews.length===0&&<li className="is-quiet">{say('この版に対する確認の記録はありません。','No checks were recorded for this version.')}</li>}
      </ul>
    </details>
    </section>
    <section className="result-choice-panel" aria-labelledby="result-choice-title">
      <div><h3 id="result-choice-title" className="result-step">{say('03 使う版を選ぶ','03 Choose a version')}</h3><p className="result-choice-file">{file.logical_path} · {say('版','Version')} {file.revision}</p><p className="result-choice-help">{say('採用は保存する版の選択です。内容を確認してから選んでください。','Selecting a version chooses what to save. Review its content before making your choice.')}</p></div>
      <div className="result-use"><span className="review-choice">{adopted?.revision===file.revision?<span className="chosen-pill" ref={choiceRef} tabIndex={-1}><b aria-hidden="true">★</b>{say('あなたが選んだ版','Your selected version')}</span>:say('まだ採用していない候補','Not yet selected by you')}</span>{run.access?.can_write!==false&&adopted?.revision!==file.revision&&<button data-adopt className={pass?'btn signal':'btn adopt-caution'} disabled={busy||!readReady} onClick={useVersion}>{pass?say('この版を使う','Use this version'):concern?say('指摘が残ったまま、この版を使う','Use this version with open findings'):say('未確認のまま、この版を使う','Use this version unverified')}</button>}<span role="status">{note}</span></div>
      {run.access?.can_write===false&&<p className="result-choice-help">{say('閲覧権限では、採用する版を変更できません。','Read-only access cannot change the selected version.')}</p>}
      {selectedCount>0&&<div className="result-selected-export"><div><strong>{say(`${selectedCount}件の採用版を保存する`,`Save ${selectedCount} selected ${selectedCount===1?'file':'files'}`)}</strong><p>{say('採用した版と作業記録をZIPで取得します。','Download the selected versions and work record as a ZIP.')}</p></div><a className="btn signal" href={browserApiUrl(`/api/runs/${run.run_id}/export?fmt=zip&selection=adopted`)}>{say('採用したファイルを保存','Save selected files')} <span aria-hidden="true">↓</span></a></div>}
    </section>
    {detail?.text!=null&&<details className="result-edit-options"><summary>{say('修正・コピーの編集','Request a change or edit a copy')}</summary><ArtifactWorkbench key={`${file.artifact_id}:${file.revision}:${file.sha256}`} file={file} text={detail.text} previous={list[list.findIndex(f=>f.revision===file.revision)-1]?.revision} onDirection={onDirection}/></details>}
    <div className="result-latest-export"><div><strong>{say('最新版をまとめて取得','Get every latest version')}</strong><p>{say('採用状況にかかわらず、各ファイルの最新版と作業記録をZIPで取得します。','Download each file’s latest version and the work record as a ZIP, regardless of your selections.')}</p></div><a className="btn ghost" href={browserApiUrl(`/api/runs/${run.run_id}/export?fmt=zip`)}>{say('最新のファイルをまとめて取得','Get all latest files')}</a></div>
  </section>
}

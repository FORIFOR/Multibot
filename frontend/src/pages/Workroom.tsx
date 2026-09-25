import { botName } from '../lib/journey'
import { useCallback, useEffect, useRef, useState, lazy, Suspense } from 'react'
import type { FormEvent } from 'react'
import { api, money, fmtTime, type RunDetail, type ChatMessage, type Artifact, type Event, type Approval } from '../lib/api'
import { getLang } from '../lib/i18n'
import { botActivity, botStateLabel } from '../lib/bot-presentation'
import { friendlyWorkText, coordinatorPlanned, outcomeLabel, friendlyReason, teamOrder, defaultPanel, requestedPanel, resultFiles, statusLabel, stateTone, roleLabel, isSettled, type JourneyPanel } from '../lib/journey'
import { Link } from '../lib/router'
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
function hasCheckRecord(file: Artifact, evidence: any, events: Event[]): boolean {
  const exact = (target: any) => target?.artifact_id === file.artifact_id && target?.revision === file.revision && target?.sha256 === file.sha256
  return [...(evidence?.checks || []), ...(evidence?.delivery_checks || [])].some((c: any) => exact(c.target)) || (evidence?.reviews || []).some((r: any) => (r.target_artifacts || []).some(exact))
    || events.some(e => ((e.type === 'check.completed' || e.type === 'delivery.checked') && exact(e.payload.target))
      || (e.type === 'review.submitted' && (e.payload.target_artifacts || []).some(exact)))
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
  const refreshRef = useRef<() => Promise<void>>(async () => {})
  const reconnectRef = useRef<() => Promise<void>>(async () => {})

  useEffect(() => {
    let alive = true, inFlight = false, cursor = 0, nextConnectAt = 0
    setRun(null); setChat([]); setEvents([]); setConnection('connecting')
    let stream: EventSource | null = null
    let queued: ReturnType<typeof setTimeout> | undefined
    const refresh = async () => {
      if (!alive || inFlight) return
      inFlight = true
      try {
        const [detail, messages, updates] = await Promise.all([api.run(runId), api.chat(runId), api.events(runId,cursor)])
        if (alive) { setRun(detail); setChat(messages); setLoadError(''); if(updates.length){cursor=updates.at(-1)!.seq;setEvents(old=>[...old,...updates])} if(!streamOpen() && detail.live && !isSettled(detail.status)) connect() }
        return detail
      } catch { if (alive) setLoadError(say('最新の状態を取得できません。表示内容が古い可能性があります。', 'Could not refresh the work. The displayed information may be out of date.')) }
      finally { inFlight = false }
    }
    const schedule = () => { if (!queued) queued = setTimeout(() => { queued = undefined; void refresh() }, 100) }
    // The stream is only a change signal; the fetches above carry the data. Start it after the last event
    // already loaded so a reconnect does not replay the whole history, and keep one open stream at a time.
    const streamOpen = () => !!stream && stream.readyState !== EventSource.CLOSED
    const connect = () => {
      stream?.close()
      if (!alive || Date.now() < nextConnectAt) return
      stream = new EventSource(`/api/runs/${encodeURIComponent(runId)}/stream?after_seq=${cursor}`)
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
    refreshRef.current = async () => { await refresh() }; reconnectRef.current = ensureStream
    void ensureStream()
    // Resync after missed SSE events and external resume; only while visible.
    const timer = setInterval(() => { if (!document.hidden) void refresh() }, 5000)
    document.addEventListener('visibilitychange', foreground)
    window.addEventListener('pageshow', foreground)
    return () => { alive = false; stream?.close(); clearInterval(timer); clearTimeout(queued); document.removeEventListener('visibilitychange', foreground); window.removeEventListener('pageshow', foreground) }
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
  const reviewNotes: string[] = [...new Set([...run.tasks.flatMap(t => [t.blocked_reason, ...(t.result?.unverified || [])]), ...(run.final_report?.narrative?.unresolved || [])].filter((v): v is string => !!v))]
  // A review of another version is not evidence for this file.
  const evidence = run.final_report?.evidence
  const latestFiles = [...new Map(files.map(f => [f.artifact_id, f] as const).sort((a, b) => a[1].revision - b[1].revision)).values()]
  const uncheckedFiles = latestFiles.filter(f => !hasCheckRecord(f, evidence, events)).length
  // What the coordinator says must follow the adoption that already happened, not keep asking for it.
  const adoptedList = Object.entries(run.artifact_selection || {})
  const adoptedUnverified = adoptedList.filter(([artifactId, selection]) => {
    const file = run.artifacts.find(a => a.artifact_id === artifactId && a.revision === selection.revision)
    return !file || !hasCheckRecord(file, evidence, events)
  }).length
  // Who owns which task, so that "t2" in a model's own words can be shown as that teammate's work.
  const owners: Record<string,string> = Object.fromEntries(run.tasks.map(t => { const a = run.config_snapshot?.agents?.[t.spec.owner]; return [t.spec.id, a?.display_name || botName(a?.role || t.spec.owner, getLang())] }))
  const runnable = ['created','queued','planning','running'].includes(run.status)
  // Runtime wording stays available on hover and in the detailed record; the everyday view says it plainly.
  const noteCount = (run.blocked_reason ? 1 : 0) + reviewNotes.length
  const notices = noteCount > 0 ? <details className="room-notes">
    <summary>{say('確認事項','Needs attention')}（{noteCount}）</summary>
    <ul>
      {run.blocked_reason && <li title={run.blocked_reason}><b>{say('止まった理由','Why work stopped')}</b> {friendlyReason(run.blocked_reason, getLang())}</li>}
      {reviewNotes.map((note, i) => <li key={i} title={note}>{friendlyReason(note, getLang())}</li>)}
    </ul>
  </details> : null
  return <div data-studio-panel={selectedPanel} className={`simple-workroom creation-studio desk-workroom ${files.length?'has-results':'no-results'}${paused ? ' motion-paused' : ''}`}>
    <Link to={`/runs?filter=${workFilter(new URLSearchParams(location.search).get('from'))}`} nav={nav} className="work-back">{say('← 作業一覧に戻る','← Back to work')}</Link>
    {run.provider_kind === 'fake' && <p className="demo-notice">{say('テスト表示です。実際のAIによる作業ではありません。','Test display. This is not work performed by a real AI.')}</p>}
    <section className={`work-status room-head tone-${pending.length ? 'attention' : stateTone(run.status)}`} aria-label={say('進み具合','Progress')}>
<div className="status-voice">{(() => { const m = Object.entries(run.config_snapshot?.agents || {}).find(([, a]) => a.enabled && a.role === 'master'); return m ? <BotAvatar id={m[0]} role={m[1].role} emoji={m[1].emoji} name={m[1].display_name || botName(m[1].role, getLang())} state={(() => { const mine = run.tasks.filter(t => t.spec.owner === m[0]); const raw = botActivity(mine, run.status, m[0], m[1].role, true); return coordinatorPlanned(m[1].role, mine.length, !!run.plan, raw, run.status) ? 'done' : raw })()} /> : null })()}      <div role="status"><strong>{pending.length ? say('あなたの確認が必要です','Your approval is needed') : statusLabel(run.status, getLang())}</strong><p>{run.status !== 'completed' ? null
        : adoptedList.length > 0 ? (adoptedUnverified > 0
          ? say(`使う版を${adoptedList.length}件選びました。そのうち${adoptedUnverified}件は確認の記録がないまま採用しています。`, `${adoptedList.length} version(s) chosen; ${adoptedUnverified} of them were adopted with no check record.`)
          : say(`使う版を${adoptedList.length}件選びました。ほかのファイルも記録を見てから選べます。`, `${adoptedList.length} version(s) chosen. You can review and choose the other files too.`))
        : uncheckedFiles > 0 ? say(`確認の記録がないファイルが${uncheckedFiles}件あります。中身と記録を見てから、使う版を選んでください。`,`${uncheckedFiles} file(s) have no check record. Read them and the record before choosing a version.`)
        : say('成果物と確認内容を見てから、使う版を選べます。','Review the files and checks, then choose a version to use.')}</p></div></div>
      <div className="work-actions"><span className="cost-summary">{say('使用額','Used')} {money(run.usage.cost_usd)}{run.usage.reserved_usd > 0 ? ` · ${say('処理中の確保額','Reserved')} ${money(run.usage.reserved_usd)}` : ''}</span>
        {canWrite && runnable && <button className="btn ghost" disabled={busy} onClick={() => act(() => api.cancel(runId))}>{say('作業を止める','Stop work')}</button>}
        {canWrite && run.plan && ['interrupted','partial','failed','cancelled'].includes(run.status) && <details className="desk-resume"><summary className="btn signal">{say('続きを進める','Continue work')}</summary><div><p>{say('途中の作業を再実行する場合があります。送信済みの資料・外部処理は取り消されません。','Unfinished tasks may run again. Sent material and completed external effects cannot be undone.')}</p><button className="btn signal" disabled={busy} onClick={() => act(() => api.resume(runId))}>{say('確認して再開','Confirm and continue')}</button></div></details>}
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
        <section id="room-team" className="simple-team-room room-team" aria-label={say('チームの様子','Your team')}>
      <div className="team-section-heading"><h2>{say('AIチーム','AI team')}</h2><button type="button" className="btn ghost" aria-pressed={paused} onClick={()=>setPaused(!paused)}>{paused?say('動きを再開','Resume animation'):say('動きを止める','Pause animation')}</button></div><ol className="team-stage">{teamOrder(Object.entries(run.config_snapshot?.agents || {}).filter(([,a]) => a.enabled && (run.inputs.team_selection !== 'adaptive' || !!run.config_snapshot?.team_recommendation || a.role === 'master'))).map(([id,a]) => {
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
        </section>
        <div id="room-request"><details className="simple-request pane" aria-label={say("お願いの内容","Your request")}><summary>{say('資料と前提','Materials & context')}</summary>
      {!run.inputs.text && run.inputs.files.length === 0 && run.inputs.urls.length === 0 && <p className="simple-empty">{say('資料や参照先は添えられていません。','No files or references were attached.')}</p>}
      {run.inputs.text && <details className="request-text"><summary>{say('添えた文章を見る','Show the attached text')}</summary><pre>{run.inputs.text}</pre></details>}{run.inputs.files.length > 0 && <p>{say('渡した資料','Attached files')}: {run.inputs.files.map(f => f.name).join(' / ')}</p>}
      {run.inputs.urls.length > 0 && <p className="request-urls">{say('参照先','References')}: {run.inputs.urls.join(' / ')}</p>}
      {!!run.plan?.assumptions.length && <div><h3>{say('進めるうえでの前提','Working assumptions')}</h3><ul>{run.plan.assumptions.map((a, i) => <li key={i}>{a}</li>)}</ul></div>}
    </details></div>

      </div>
      <div className="room-main">
      <div id="work-conversation" tabIndex={-1}><TeamConversation key={runId} run={run} chat={chat} events={events} onOpenArtifact={ref=>{setArtifactTarget({id:ref.artifact_id,revision:ref.revision,sha256:ref.sha256});select('results')}} connection={loadError ? 'reconnecting' : connection}><Direction run={run} refresh={refresh} text={directionDraft} setText={setDirectionDraft} /></TeamConversation></div>
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

function Direction({ run, refresh, text, setText }: { run: RunDetail; refresh: () => Promise<void>; text: string; setText: (value: string) => void }) {
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
    <pre>{JSON.stringify(a.payload.payload ?? a.payload,null,2)}</pre><p>{say('有効期限','Expires')}: {fmtTime(a.expires_at)}{a.payload.estimated_cost_usd!=null ? ` · ${say('見積もり','Estimate')} $${a.payload.estimated_cost_usd}`:''}</p>
    {readOnly?<p>{say('閲覧権限では承認できません。','Read-only access cannot approve this action.')}</p>:<div className="row"><button className="btn signal" disabled={busy} onClick={()=>resolve(a,'approve')}>{say('この内容で承認','Approve this action')}</button><button className="btn ghost" disabled={busy} onClick={()=>resolve(a,'reject')}>{say('承認しない','Decline')}</button></div>}
  </article>)}</>
}

type ArtifactDetail = Artifact & { text?: string; checks: Event[]; reviews: Event[] }
function Deliverables({run,events,refresh,target,clearTarget,onDirection}:{run:RunDetail;events:Event[];refresh:()=>Promise<void>;target:{id:string;revision:number;sha256:string}|null;clearTarget:()=>void;onDirection:(text:string)=>void}) {
  const [showSource,setShowSource]=useState(false)
  const [readAttempt,setReadAttempt]=useState(0)
  const [recordOpen,setRecordOpen]=useState(false)
  const shown=useRef(''), focusChoice=useRef(false), choiceRef=useRef<HTMLSpanElement>(null)
  // Use the same exact revision/hash rule as the status line.
  const evidence=run.final_report?.evidence
  const unchecked=new Set<string>(resultFiles(run.artifacts).filter((f,_,all)=>f.revision===Math.max(...all.filter(x=>x.artifact_id===f.artifact_id).map(x=>x.revision))).filter(f=>!hasCheckRecord(f,evidence,events)).map(f=>f.artifact_id))
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
  const [detail,setDetail]=useState<ArtifactDetail|null>(null),[error,setError]=useState(''),[note,setNote]=useState(''),[busy,setBusy]=useState(false)
  const lock=useRef(false)
  useEffect(()=>{let alive=true;const key=file?`${file.artifact_id}@${file.revision}`:'';if(shown.current!==key){shown.current=key;setDetail(null);setNote('')}setError('');if(file)api.artifact(run.run_id,file.artifact_id,file.revision).then(d=>{if(alive)setDetail(d)}).catch(()=>{if(alive)setError(say('ファイルを読み込めませんでした。','Could not load the file.'))});return()=>{alive=false}},[run.run_id,file?.artifact_id,file?.revision,run.last_seq,readAttempt])
  useEffect(()=>{if(focusChoice.current&&adopted?.revision===file?.revision){focusChoice.current=false;choiceRef.current?.focus()}},[adopted?.revision,file?.revision])
  if((selection&&!file)||(target&&file?.artifact_id===target.id&&file.revision===target.revision&&file.sha256!==target.sha256))return <p role="alert">{say('参照された版を確認できません。','The referenced version could not be verified.')} <button className="btn ghost" onClick={()=>{clearTarget();setSelection(null)}}>{say('成果物一覧へ','Back to results')}</button></p>
  if(!file)return <div className="result-empty pane"><span aria-hidden="true">📦</span><h2>{say('成果物はまだありません','No results yet')}</h2></div>
  const exact=(target:any)=>target?.artifact_id===file.artifact_id&&target?.revision===file.revision&&target?.sha256===file.sha256
  const checks=(detail?.checks||[]).filter(e=>exact(e.payload.target))
  const reviews=(detail?.reviews||[]).filter(e=>(e.payload.target_artifacts||[]).some(exact))
  const reviewAuthor=(event:Event)=>{const agent=run.config_snapshot?.agents?.[event.actor_id];return agent?.display_name || (agent?botName(agent.role,getLang()):event.actor_id || say('確認者','Reviewer'))}
  const outcomes=[...checks.map(e=>e.payload.result?.status),...reviews.flatMap(e=>(e.payload.results||[]).map((r:any)=>r.status))]
  const pass=outcomes.length>0&&outcomes.every(s=>s==='pass'), concern=outcomes.some(s=>s!=='pass')
  const isMarkdown=/markdown/.test(file.media_type)||/\.(md|markdown)$/i.test(file.logical_path)
  // The adopt button disappears once pressed; hand focus to what replaced it so keyboard users are not dropped on <body>.
  const useVersion=async()=>{if(lock.current)return;lock.current=true;setBusy(true);setNote('');try{await api.adoptArtifact(run.run_id,file.artifact_id,{revision:file.revision,expected_selected_revision:adopted?.revision ?? 0});setNote(say('この版を使うことにしました。','This version is now selected.'));focusChoice.current=true;await refresh()}catch{setError(say('選択を保存できませんでした。再読み込みしてお試しください。','Could not save your choice. Refresh and try again.'))}finally{lock.current=false;setBusy(false)}}
  return <section className="pane simple-deliverables"><header><h2>{say('できたもの','Your results')}</h2>{Object.keys(run.artifact_selection || {}).length > 0 && <a className="btn ghost" href={`/api/runs/${run.run_id}/export?fmt=zip&selection=adopted`}>{say('採用したファイルを保存','Save selected files')}</a>}<a className="btn ghost" href={`/api/runs/${run.run_id}/export?fmt=zip`}>{say('最新のファイルをまとめて取得','Get all latest files')}</a></header>
    <div className="result-file-list" aria-label={say('ファイルを選ぶ','Choose a file')}>{[...versions.entries()].map(([key,items])=><button className={key===id?'active':''} type="button" aria-pressed={key===id} key={key} onClick={()=>{clearTarget();setSelection({id:key,revision:run.artifact_selection?.[key]?.revision||items[items.length-1].revision})}}><span aria-hidden="true">📄</span>{items[items.length-1].logical_path}{run.artifact_selection?.[key]&&<span className="tab-chosen" title={say('あなたが選んだ版があります','You selected a version')}>{say('採用','Chosen')}</span>}{unchecked.has(key)&&<span className="tab-mark" role="img" aria-label={say('確認の記録なし','No check record')} title={say('確認の記録なし','No check record')}>?</span>}</button>)}</div>
    <div className="result-decide">
    <div className={`result-review-summary is-${pass?'pass':concern?'concern':'none'}`}>
      <span className="review-state"><b aria-hidden="true">{pass?'✓':concern?'!':'?'}</b>{pass?say('この版の記録された確認は通過','Recorded checks passed for this version'):concern?say('この版には未確認・要修正の項目があります','This version has unchecked or flagged items'):say('未確認：この版の確認記録はまだありません','Unverified: No check record for this version yet')}</span>
      <button type="button" className="review-link" onClick={()=>{setRecordOpen(true);setTimeout(()=>document.getElementById('result-record')?.scrollIntoView({block:'center'}),0)}}>{say('確認の記録を見る','See the check record')}</button>
    </div>
    {error&&<p className="work-warning" role="alert">{error} <button className="btn ghost" onClick={()=>setReadAttempt(n=>n+1)}>{say('再読み込み','Refresh')}</button></p>}
    <div className="result-use">{isMarkdown&&<button type="button" className="btn ghost" aria-pressed={showSource} onClick={()=>setShowSource(!showSource)}>{showSource?say('読みやすく表示','Show formatted'):say('原文を表示','Show source')}</button>}{run.access?.can_write!==false&&adopted?.revision!==file.revision&&<button data-adopt className={pass?'btn signal':'btn adopt-caution'} disabled={busy||!detail} onClick={useVersion}>{pass?say('この版を使う','Use this version'):concern?say('指摘が残ったまま、この版を使う','Use this version with open findings'):say('未確認のまま、この版を使う','Use this version unverified')}</button>}<a className="btn ghost" href={api.artifactRawUrl(run.run_id,file.artifact_id,file.revision)} target="_blank" rel="noreferrer">{say('このファイルを開く','Open this file')}</a><span className="review-choice">{adopted?.revision===file.revision?<span className="chosen-pill" ref={choiceRef} tabIndex={-1}><b aria-hidden="true">★</b>{say('あなたが選んだ版','Your selected version')}</span>:say('まだ採用していない候補','Not yet selected by you')}</span><span role="status">{note}</span></div>
    </div>
    {detail?.text!=null&&<ArtifactWorkbench key={`${file.artifact_id}:${file.revision}:${file.sha256}`} file={file} text={detail.text} previous={list[list.findIndex(f=>f.revision===file.revision)-1]?.revision} onDirection={onDirection}/>}
    <div className="result-reader" role="region" aria-label={say(`成果物：${file.logical_path}`,`Result: ${file.logical_path}`)} tabIndex={0}>{file.media_type.includes('html')?<iframe title={file.logical_path} sandbox="" src={api.artifactRawUrl(run.run_id,file.artifact_id,file.revision)}/>:isMarkdown&&detail?.text!=null&&!showSource?<Markdown text={detail.text} className="md result-md"/>:<pre>{detail?.text ?? (detail?say('この形式は別のウィンドウで開いてください。','Open this file in a new window to view it.'):say('読み込み中…','Loading…'))}</pre>}</div>
    <details id="result-record" className="result-record" open={recordOpen} onToggle={e=>setRecordOpen(e.currentTarget.open)}><summary>{say('版と確認の記録','Versions & check record')}</summary>
      <div className="row">{list.map(f=><button key={f.revision} className="btn ghost" aria-pressed={file.revision===f.revision} onClick={()=>{clearTarget();setSelection({id:f.artifact_id,revision:f.revision})}}>{say('版','Version')} {f.revision}</button>)}</div>
      <p>{say('確認はこの版に対する記録です。内容の完全な正しさを保証するものではありません。','Checks apply to this exact version; they do not guarantee that every statement is correct.')}</p>
      <p>{file.logical_path} · {say('版','Version')} {file.revision} · <span title={file.sha256}>{say('この版の識別子','Version identifier')} <code>{file.sha256.slice(0,12)}</code></span></p>
      <ul className="check-record">
        {checks.map(e=><li key={e.event_id}><span className={`check-mark is-${e.payload.result?.status||'unknown'}`}>{outcomeLabel(e.payload.result?.status,getLang())}</span>{e.type==='delivery.checked'?say('依頼した必須条件','Required delivery conditions'):say('自動チェック','Automatic check')} <code>{String(e.payload.kind||e.payload.result?.kind||'')}</code>{e.payload.result?.problems?.length?<span className="check-detail"> — {e.payload.result.problems.join(' / ')}</span>:null}{e.payload.result?.detail?<span className="check-detail"> — {String(e.payload.result.detail).slice(0,240)}</span>:null}</li>)}
        {reviews.flatMap(e=>(e.payload.results||[]).map((r:any,n:number)=><li key={e.event_id+n}><span className={`check-mark is-${r.status}`}>{outcomeLabel(r.status,getLang())}</span>{say(`${reviewAuthor(e)}の確認`,`Review by ${reviewAuthor(e)}`)} <code>{String(r.acceptance_id||'')}</code>{r.evidence||r.reason?<span className="check-detail"> — {String(r.evidence||r.reason).slice(0,240)}</span>:null}</li>))}
        {checks.length+reviews.length===0&&<li className="is-quiet">{say('この版に対する確認の記録はありません。','No checks were recorded for this version.')}</li>}
      </ul>
    </details>
  </section>
}

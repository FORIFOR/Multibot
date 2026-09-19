import { useCallback, useEffect, useRef, useState, lazy, Suspense } from 'react'
import type { FormEvent } from 'react'
import { api, money, fmtTime, type RunDetail, type ChatMessage, type Artifact, type Event, type Approval } from '../lib/api'
import { getLang } from '../lib/i18n'
import { botActivity, botStateLabel } from '../lib/bot-presentation'
import { coordinatorPlanned, outcomeLabel, friendlyReason, teamOrder, defaultPanel, requestedPanel, resultFiles, statusLabel, stateTone, roleLabel, isSettled, type JourneyPanel } from '../lib/journey'
import Journey from '../components/Journey'
import BotAvatar from '../components/BotAvatar'
import Markdown from '../components/Markdown'
import '../journey.css'
import '../welcome.css'

// Full audit tools are preserved, but loaded only when the user asks for them.
const Inspector = lazy(() => import('./RunView'))
const say = (ja: string, en: string) => getLang() === 'en' ? en : ja
const eventTypes = ['run.created','run.started','run.queued','run.completed','run.partial','run.failed','run.cancelled','run.interrupted','run.resumed','run.blocked','plan.accepted','plan.milestone','task.started','task.updated','task.ready','task.waiting','task.accepted','task.partial','task.failed','task.blocked','task.review_pending','task.cancelled','task.interrupted','artifact.published','artifact.adopted','review.submitted','check.completed','approval.requested','approval.resolved','instruction.received','message.sent']

export default function Workroom({ runId, nav }: { runId: string; nav: (path: string) => void }) {
  const [run, setRun] = useState<RunDetail | null>(null)
  const [chat, setChat] = useState<ChatMessage[]>([])
  const [loadError, setLoadError] = useState('')
  const [actionError, setActionError] = useState('')
  const [busy, setBusy] = useState(false)
  const actionLock = useRef(false)
  const [goalOpen, setGoalOpen] = useState(false)
  const [panel, setPanel] = useState<JourneyPanel | null>(() => requestedPanel(location.search))
  const queryTab = new URLSearchParams(location.search).get('tab')
  const [inspect, setInspect] = useState(() => ['timeline','report','chat'].includes(queryTab || ''))
  const [approvalsOpen, setApprovalsOpen] = useState(queryTab === 'approvals')
  const [paused, setPaused] = useState(false)
  const [directionDraft, setDirectionDraft] = useState('')
  const refreshRef = useRef<() => Promise<void>>(async () => {})
  const reconnectRef = useRef<() => void>(() => {})

  useEffect(() => {
    let alive = true, inFlight = false
    let stream: EventSource | null = null
    let queued: ReturnType<typeof setTimeout> | undefined
    const refresh = async () => {
      if (!alive || inFlight) return
      inFlight = true
      try {
        const [detail, messages] = await Promise.all([api.run(runId), api.chat(runId)])
        if (alive) { setRun(detail); setChat(messages); setLoadError('') }
      } catch { if (alive) setLoadError(say('最新の状態を取得できません。表示内容が古い可能性があります。', 'Could not refresh the work. The displayed information may be out of date.')) }
      finally { inFlight = false }
    }
    const schedule = () => { if (!queued) queued = setTimeout(() => { queued = undefined; void refresh() }, 100) }
    const connect = () => {
      stream?.close()
      if (!alive) return
      stream = new EventSource(`/api/runs/${encodeURIComponent(runId)}/stream`)
      for (const type of eventTypes) stream.addEventListener(type, schedule)
      stream.addEventListener('end', () => { stream?.close(); stream = null; schedule() })
      stream.onerror = () => { void refresh() }
    }
    const foreground = () => { if (!document.hidden) { void refresh(); connect() } }
    refreshRef.current = refresh; reconnectRef.current = connect
    void refresh(); connect()
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
    try { await fn(); await refresh(); reconnectRef.current() }
    catch { setActionError(say('操作を完了できませんでした。状態を確認して、もう一度お試しください。', 'The action did not finish. Check the status and try again.')) }
    finally { actionLock.current = false; setBusy(false) }
  }
  if (!run) return <section className="simple-loading" aria-live="polite"><h1>{loadError || say('チームの様子を読み込んでいます…', 'Opening your work…')}</h1><button className="btn ghost" onClick={refresh}>{say('もう一度読み込む','Try again')}</button></section>
  const files = resultFiles(run.artifacts)
  const selectedPanel = panel || defaultPanel(run.status, files.length)
  const pending = run.approvals.filter(a => a.status === 'pending')
  const canWrite = run.access?.can_write !== false
  const select = (next: JourneyPanel) => {
    setPanel(next)
    // One page: every area is always on screen. Choosing a step brings its area into view.
    const calm = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    document.getElementById(`room-${next}`)?.scrollIntoView({ block: 'start', behavior: calm ? 'auto' : 'smooth' })
    const url = new URL(location.href); url.searchParams.set('view', next); url.searchParams.delete('tab')
    history.replaceState(history.state, '', url.pathname + url.search + url.hash)
  }
  const reviewNotes: string[] = [...new Set([...run.tasks.flatMap(t => [t.blocked_reason, ...(t.result?.unverified || [])]), ...(run.final_report?.narrative?.unresolved || [])].filter((v): v is string => !!v))]
  // A file counts as checked only if this exact latest version has a recorded check, or its task has a recorded review.
  const evidence = run.final_report?.evidence
  const latestFiles = [...new Map(files.map(f => [f.artifact_id, f] as const).sort((a, b) => a[1].revision - b[1].revision)).values()]
  const uncheckedFiles = evidence ? latestFiles.filter(f => !(evidence.checks || []).some((c: any) => c.target?.artifact_id === f.artifact_id && c.target?.revision === f.revision) && !(evidence.reviews || []).some((r: any) => r.target_task_id === f.task_id)).length : 0
  const runnable = ['created','queued','planning','running'].includes(run.status)
  // Runtime wording stays available on hover and in the detailed record; the everyday view says it plainly.
  const noteCount = (run.blocked_reason ? 1 : 0) + reviewNotes.length
  const notices = noteCount > 0 ? <details className="room-notes" open={noteCount <= 2}>
    <summary>{say('まだ確認が必要なこと','Still needs checking')}（{noteCount}）</summary>
    <ul>
      {run.blocked_reason && <li title={run.blocked_reason}><b>{say('止まった理由','Why work stopped')}</b> {friendlyReason(run.blocked_reason, getLang())}</li>}
      {reviewNotes.map((note, i) => <li key={i} title={note}>{friendlyReason(note, getLang())}</li>)}
    </ul>
  </details> : null
  return <div className={`simple-workroom${paused ? ' motion-paused' : ''}`}>
    <Journey current={selectedPanel} onSelect={select} />
    {run.provider_kind === 'fake' && <p className="demo-notice">{say('テスト表示です。実際のAIによる作業ではありません。','Test display. This is not work performed by a real AI.')}</p>}
    <section className={`work-status room-head tone-${pending.length ? 'attention' : stateTone(run.status)}`} aria-label={say('進み具合','Progress')}>
<div className="status-voice">{(() => { const m = Object.entries(run.config_snapshot?.agents || {}).find(([, a]) => a.enabled && a.role === 'master'); return m ? <BotAvatar id={m[0]} role={m[1].role} emoji={m[1].emoji} name={m[1].display_name || roleLabel(m[1].role, getLang())} state={(() => { const mine = run.tasks.filter(t => t.spec.owner === m[0]); const raw = botActivity(mine, run.status, m[0], m[1].role, true); return coordinatorPlanned(m[1].role, mine.length, !!run.plan, raw, run.status) ? 'done' : raw })()} /> : null })()}      <div role="status"><strong>{pending.length ? say('あなたの確認が必要です','Your approval is needed') : statusLabel(run.status, getLang())}</strong><p>{run.status === 'completed' ? (uncheckedFiles > 0 ? say(`確認の記録がないファイルが${uncheckedFiles}件あります。中身と記録を見てから、使う版を選んでください。`,`${uncheckedFiles} file(s) have no check record. Read them and the record before choosing a version.`) : say('成果物と確認内容を見てから、使う版を選べます。','Review the files and checks, then choose a version to use.')) : say('途中でできたものも、この画面の「できたもの」で確認できます。','Work in progress appears under “Your results” on this page.')}</p></div></div>
      <div className="work-actions"><span className="cost-summary">{say('使用額','Used')} {money(run.usage.cost_usd)}{run.usage.reserved_usd > 0 ? ` · ${say('処理中の確保額','Reserved')} ${money(run.usage.reserved_usd)}` : ''}</span>
        {canWrite && runnable && <button className="btn ghost" disabled={busy} onClick={() => act(() => api.cancel(runId))}>{say('作業を止める','Stop work')}</button>}
        {canWrite && ['interrupted','partial','failed','cancelled'].includes(run.status) && <button className="btn signal" disabled={busy} onClick={() => act(() => api.resume(runId))}>{say('続きを進める','Continue work')}</button>}
        <button className="btn ghost" onClick={() => nav('/')}>{say('新しくお願いする','New request')}</button>
      </div>
      <header className="simple-run-heading room-goal">
        <p className="simple-eyebrow">{say('お願いしたこと','Your request')}</p>
        <h1 className={goalOpen ? undefined : 'goal-clamp'} title={goalOpen ? undefined : run.goal}>{run.goal}</h1>
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
    <div className="room-grid">
      <div className="room-side">
        {notices}
        <section id="room-team" className="simple-team-room room-team" aria-label={say('チームの様子','Your team')}>
      <ol className="team-stage">{teamOrder(Object.entries(run.config_snapshot?.agents || {}).filter(([,a]) => a.enabled)).map(([id,a]) => {
        const tasks = run.tasks.filter(t => t.spec.owner === id), raw = botActivity(tasks, run.status, id, a.role, a.enabled)
        const state = coordinatorPlanned(a.role, tasks.length, !!run.plan, raw, run.status) ? 'done' : raw
        const task = tasks.find(t => t.status === 'running') || tasks.find(t => !['accepted','cancelled'].includes(t.status)) || tasks[tasks.length - 1]
        const active = ['thinking','researching','building','reviewing'].includes(state)
        return <li className={`simple-bot state-${state}${active ? ' is-active' : ''}`} key={id}>
          <div className="bot-floor"><BotAvatar id={id} role={a.role} name={a.display_name || roleLabel(a.role,getLang())} emoji={a.emoji} state={state} size="stage" /></div>
          <h2>{a.display_name || roleLabel(a.role,getLang())}</h2>
          <span className="simple-bot-state" role="status">{botStateLabel(state,getLang())}</span>
          {task ? <p className="bot-says">{task.spec.objective}</p> : <p className="bot-says is-quiet">{a.role === 'master' && run.plan ? say('進め方を決めて、みんなに頼みました','Planned the work and handed it out') : isSettled(run.status) ? say('今回は出番がありませんでした','No assignment in this request') : say('出番を待っています','Waiting for a turn')}</p>}
        </li>
      })}</ol>
      {Object.keys(run.config_snapshot?.agents || {}).length === 0 && <p className="simple-empty">{say('チームの準備ができると、ここに仲間が表示されます。','Your teammates appear here once the team is ready.')}</p>}
        </section>
        <div id="room-request"><section className="simple-request pane" aria-label={say("お願いの内容","Your request")}><h2>{say('お願いに添えたもの','What came with your request')}</h2>
      {!run.inputs.text && run.inputs.files.length === 0 && run.inputs.urls.length === 0 && <p className="simple-empty">{say('資料や参照先は添えられていません。','No files or references were attached.')}</p>}
      {run.inputs.text && <details className="request-text"><summary>{say('添えた文章を見る','Show the attached text')}</summary><pre>{run.inputs.text}</pre></details>}{run.inputs.files.length > 0 && <p>{say('渡した資料','Attached files')}: {run.inputs.files.map(f => f.name).join(' / ')}</p>}
      {run.inputs.urls.length > 0 && <p className="request-urls">{say('参照先','References')}: {run.inputs.urls.join(' / ')}</p>}
      {!!run.plan?.assumptions.length && <div><h3>{say('進めるうえでの前提','Working assumptions')}</h3><ul>{run.plan.assumptions.map((a, i) => <li key={i}>{a}</li>)}</ul></div>}
    </section></div>
      <section className="team-conversation pane"><header><h2>{say('チームのやりとり','Team conversation')}</h2><button className="btn ghost" aria-pressed={paused} onClick={() => setPaused(!paused)}>{say('動きを止める','Pause animation')}</button></header>
        <div className="conversation-content">{chat.length ? chat.slice(-5).map(m => <article className="simple-message" key={m.event_id}>
          <BotAvatar id={m.from} role={run.config_snapshot?.agents?.[m.from]?.role} emoji={run.config_snapshot?.agents?.[m.from]?.emoji} name={run.config_snapshot?.agents?.[m.from]?.display_name} state="idle" size="micro" />
          <div><div className="simple-message-by"><strong>{run.config_snapshot?.agents?.[m.from]?.display_name || roleLabel(run.config_snapshot?.agents?.[m.from]?.role || m.from,getLang())}</strong><span>→ {run.config_snapshot?.agents?.[m.to]?.display_name || roleLabel(run.config_snapshot?.agents?.[m.to]?.role || m.to,getLang())}</span><time>{fmtTime(m.recorded_at)}</time></div><p>{m.text}</p></div>
        </article>) : <p className="simple-empty">{say('やりとりが届くと、ここで見られます。','Delivered team messages will appear here.')}</p>}
        {chat.length > 5 && <button className="btn ghost" onClick={() => { setInspect(true); setTimeout(() => document.getElementById('run-inspector')?.scrollIntoView({block:'start'}), 0) }}>{say('すべてのやりとりを見る','See the full conversation')}</button>}</div>
        <Direction run={run} refresh={refresh} text={directionDraft} setText={setDirectionDraft} />
      </section>
      </div>
      <div id="room-results" className="room-main"><section className="simple-results" aria-label={say('できたもの','Your results')}>
      {run.status !== 'completed' && <p className="work-warning">{isSettled(run.status) ? say('依頼全体は完了していません。使える途中成果を確認できます。','The request is not complete. These are the available partial results.') : say('作業途中の内容です。確認・修正で変わることがあります。','These are drafts. They may change as the team checks and revises them.')}</p>}
      <Deliverables key={runId} run={run} refresh={refresh} />
    </section></div>
    </div>
    <details id="run-inspector" className="work-inspector" open={inspect} onToggle={e => setInspect(e.currentTarget.open)}>
      <summary>{say('詳しい作業記録・設定','Detailed work record & controls')}</summary>
      {inspect && <Suspense fallback={<p>{say('詳細を読み込んでいます…','Loading details…')}</p>}><Inspector runId={runId} nav={nav} /></Suspense>}
    </details>
  </div>
}

function Direction({ run, refresh, text, setText }: { run: RunDetail; refresh: () => Promise<void>; text: string; setText: (value: string) => void }) {
  const [busy,setBusy] = useState(false), [note,setNote] = useState(''), [error,setError] = useState('')
  const lock = useRef(false)
  const allowed = run.access?.can_write !== false && ['created','queued','planning','running'].includes(run.status)
  const send = async (e: FormEvent) => {
    e.preventDefault(); if (lock.current || !allowed || !text.trim()) return
    lock.current = true; setBusy(true); setError(''); setNote('')
    try { await api.instruction(run.run_id,{text:text.trim(),kind:'change'}); setText(''); setNote(say('受け取りました。次に始まる作業へ渡します。','Received. This will be passed to the next task.')); await refresh() }
    catch { setError(say('送れませんでした。入力は残してあります。','Could not send. Your text has been kept.')) }
    finally { lock.current=false;setBusy(false) }
  }
  return <form className="simple-direction" onSubmit={send}>
    <label htmlFor="team-direction">{say('チームに伝える','Tell your team')}</label>
    <p id="direction-note">{allowed ? say('次に始まる作業へ渡します。今の計画は自動では書き換えません。','Passed to the next task. The current plan is not automatically rewritten.') : say('追加の指示は、作業を再開してから送れます。','Resume the work before sending another direction.')}</p>
    <textarea id="team-direction" className="input" aria-describedby="direction-note" placeholder={say('例：もっと短く、やさしい文章にして','For example: make it shorter and easier to read')} value={text} onChange={e=>setText(e.target.value)} maxLength={4000} disabled={!allowed || busy} />
    <div className="direction-footer"><span role="status">{note}</span><button className="btn signal" type="submit" disabled={!allowed || busy || !text.trim()}>{busy?say('送っています…','Sending…'):say('伝える','Send')}</button></div>
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
function Deliverables({run,refresh}:{run:RunDetail;refresh:()=>Promise<void>}) {
  const [showSource,setShowSource]=useState(false)
  const [recordOpen,setRecordOpen]=useState(false)
  // Same rule as the status line: checked means this exact latest version has a recorded check, or its task a recorded review.
  const evidence=run.final_report?.evidence
  const unchecked=new Set<string>(evidence?resultFiles(run.artifacts).filter((f,_,all)=>f.revision===Math.max(...all.filter(x=>x.artifact_id===f.artifact_id).map(x=>x.revision))).filter(f=>!(evidence.checks||[]).some((c:any)=>c.target?.artifact_id===f.artifact_id&&c.target?.revision===f.revision)&&!(evidence.reviews||[]).some((r:any)=>r.target_task_id===f.task_id)).map(f=>f.artifact_id):[])
  const versions = new Map<string,Artifact[]>()
  for(const file of resultFiles(run.artifacts)){const list=versions.get(file.artifact_id)||[];list.push(file);versions.set(file.artifact_id,list)}
  for(const list of versions.values())list.sort((a,b)=>a.revision-b.revision)
  const [selection,setSelection]=useState<{id:string;revision:number}|null>(null)
  const keys=[...versions.keys()]
  const first=(keys.find(k=>versions.get(k)!.some(f=>f.media_type.includes('html')))||keys[keys.length-1]) as string|undefined
  const id=selection&&versions.has(selection.id)?selection.id:first
  const list=id?versions.get(id)||[]:[]
  const adopted=id?run.artifact_selection?.[id]:undefined
  const revision=selection&&selection.id===id?selection.revision:adopted?.revision
  const file=list.find(a=>a.revision===revision)||list[list.length-1]
  const [detail,setDetail]=useState<ArtifactDetail|null>(null),[error,setError]=useState(''),[note,setNote]=useState(''),[busy,setBusy]=useState(false)
  const lock=useRef(false)
  useEffect(()=>{let alive=true;setDetail(null);setError('');setNote('');if(file)api.artifact(run.run_id,file.artifact_id,file.revision).then(d=>{if(alive)setDetail(d)}).catch(()=>{if(alive)setError(say('ファイルを読み込めませんでした。','Could not load the file.'))});return()=>{alive=false}},[run.run_id,file?.artifact_id,file?.revision,run.last_seq])
  if(!file)return <div className="result-empty pane"><span aria-hidden="true">📦</span><h2>{say('できたものは、ここに届きます','Your results will arrive here')}</h2><p>{isSettled(run.status)?say('この作業では、成果物がまだ保存されていません。','No deliverables were saved for this work.'):say('チームの様子は2番から確認できます。','You can check on your team in step 2.')}</p></div>
  const exact=(target:any)=>target?.artifact_id===file.artifact_id&&target?.revision===file.revision&&target?.sha256===file.sha256
  const checks=(detail?.checks||[]).filter(e=>exact(e.payload.target))
  const reviews=(detail?.reviews||[]).filter(e=>(e.payload.target_artifacts||[]).some(exact))
  const outcomes=[...checks.map(e=>e.payload.result?.status),...reviews.flatMap(e=>(e.payload.results||[]).map((r:any)=>r.status))]
  const pass=outcomes.length>0&&outcomes.every(s=>s==='pass'), concern=outcomes.some(s=>s!=='pass')
  const isMarkdown=/markdown/.test(file.media_type)||/\.(md|markdown)$/i.test(file.logical_path)
  const useVersion=async()=>{if(lock.current)return;lock.current=true;setBusy(true);setNote('');try{await api.adoptArtifact(run.run_id,file.artifact_id,{revision:file.revision,expected_selected_revision:adopted?.revision});setNote(say('この版を使うことにしました。','This version is now selected.'));await refresh()}catch{setError(say('選択を保存できませんでした。再読み込みしてお試しください。','Could not save your choice. Refresh and try again.'))}finally{lock.current=false;setBusy(false)}}
  return <section className="pane simple-deliverables"><header><h2>{say('できたもの','Your results')}</h2><a className="btn ghost" href={`/api/runs/${run.run_id}/export?fmt=zip`}>{say('最新のファイルをまとめて取得','Get all latest files')}</a></header>
    <div className="result-file-list" aria-label={say('ファイルを選ぶ','Choose a file')}>{[...versions.entries()].map(([key,items])=><button className={key===id?'active':''} type="button" aria-pressed={key===id} key={key} onClick={()=>setSelection({id:key,revision:run.artifact_selection?.[key]?.revision||items[items.length-1].revision})}><span aria-hidden="true">📄</span>{items[items.length-1].logical_path}{unchecked.has(key)&&<span className="tab-mark" role="img" aria-label={say('確認の記録なし','No check record')} title={say('確認の記録なし','No check record')}>?</span>}</button>)}</div>
    <div className={`result-review-summary is-${pass?'pass':concern?'concern':'none'}`}>
      <span className="review-state"><b aria-hidden="true">{pass?'✓':concern?'!':'?'}</b>{pass?say('この版の記録された確認は通過','Recorded checks passed for this version'):concern?say('この版には未確認・要修正の項目があります','This version has unchecked or flagged items'):say('未確認：この版の確認記録はまだありません','Unverified: No check record for this version yet')}</span>
      <button type="button" className="review-link" onClick={()=>{setRecordOpen(true);setTimeout(()=>document.getElementById('result-record')?.scrollIntoView({block:'center'}),0)}}>{say('確認の記録を見る','See the check record')}</button>
      <span className="review-choice">{adopted?.revision===file.revision?say('あなたが選んだ版','Your selected version'):say('まだ採用していない候補','Not yet selected by you')}</span>
    </div>
    {error&&<p className="work-warning" role="alert">{error} <button className="btn ghost" onClick={refresh}>{say('再読み込み','Refresh')}</button></p>}
    <div className="result-reader">{file.media_type.includes('html')?<iframe title={file.logical_path} sandbox="" src={api.artifactRawUrl(run.run_id,file.artifact_id,file.revision)}/>:isMarkdown&&detail?.text!=null&&!showSource?<Markdown text={detail.text} className="md result-md"/>:<pre>{detail?.text ?? (detail?say('この形式は別のウィンドウで開いてください。','Open this file in a new window to view it.'):say('読み込み中…','Loading…'))}</pre>}</div>
    <div className="result-use">{isMarkdown&&<button type="button" className="btn ghost" aria-pressed={showSource} onClick={()=>setShowSource(!showSource)}>{showSource?say('読みやすく表示','Show formatted'):say('原文を表示','Show source')}</button>}<a className="btn ghost" href={api.artifactRawUrl(run.run_id,file.artifact_id,file.revision)} target="_blank" rel="noreferrer">{say('このファイルを開く','Open this file')}</a>{run.access?.can_write!==false&&adopted?.revision!==file.revision&&<button className="btn signal" disabled={busy||!detail} onClick={useVersion}>{say('この版を使う','Use this version')}</button>}<span role="status">{note}</span></div>
    <details id="result-record" className="result-record" open={recordOpen} onToggle={e=>setRecordOpen(e.currentTarget.open)}><summary>{say('版と確認の記録','Versions & check record')}</summary>
      <div className="row">{list.map(f=><button key={f.revision} className="btn ghost" aria-pressed={file.revision===f.revision} onClick={()=>setSelection({id:f.artifact_id,revision:f.revision})}>{say('版','Version')} {f.revision}</button>)}</div>
      <p>{say('確認はこの版に対する記録です。内容の完全な正しさを保証するものではありません。','Checks apply to this exact version; they do not guarantee that every statement is correct.')}</p>
      <p>{file.logical_path} · {say('版','Version')} {file.revision} · sha256 {file.sha256}</p>
      <ul className="check-record">
        {checks.map(e=><li key={e.event_id}><span className={`check-mark is-${e.payload.result?.status||'unknown'}`}>{outcomeLabel(e.payload.result?.status,getLang())}</span>{say('自動チェック','Automatic check')} <code>{String(e.payload.kind||e.payload.result?.kind||'')}</code>{e.payload.result?.detail?<span className="check-detail"> — {String(e.payload.result.detail).slice(0,240)}</span>:null}</li>)}
        {reviews.flatMap(e=>(e.payload.results||[]).map((r:any,n:number)=><li key={e.event_id+n}><span className={`check-mark is-${r.status}`}>{outcomeLabel(r.status,getLang())}</span>{say('確かめる係の確認','Reviewer check')} <code>{String(r.acceptance_id||'')}</code>{r.evidence||r.reason?<span className="check-detail"> — {String(r.evidence||r.reason).slice(0,240)}</span>:null}</li>))}
        {checks.length+reviews.length===0&&<li className="is-quiet">{say('この版に対する確認の記録はありません。','No checks were recorded for this version.')}</li>}
      </ul>
    </details>
  </section>
}

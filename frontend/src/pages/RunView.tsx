import { t as tr, getLang } from '../lib/i18n'
import Orb from '../components/Orb'
import Markdown from '../components/Markdown'
import BotCharacter from '../components/BotAvatar'
import { botActivity, botStateLabel } from '../lib/bot-presentation'
import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { api, fmtTime, money, TERMINAL, type Approval, type Artifact, type ArtifactSelection, type ChatMessage, type Event, type RunDetail, type TaskState, type TimelineItem } from '../lib/api'
import { Link } from '../lib/router'

type Tab = 'chat' | 'timeline' | 'report' | 'approvals'

export default function RunView({ runId, nav }: { runId: string; nav: (p: string) => void }) {
  const [run, setRun] = useState<RunDetail | null>(null)
  const [events, setEvents] = useState<Event[]>([])
  const [chat, setChat] = useState<ChatMessage[]>([])
  const [timeline, setTimeline] = useState<TimelineItem[]>([])
  const [tab, setTab] = useState<Tab>((new URLSearchParams(window.location.search).get('tab') as Tab) || 'chat')
  const [selArt, setSelArt] = useState<{ id: string; rev: number } | null>(null)
  const [selTask, setSelTask] = useState<string | null>(null)
  const [showTools, setShowTools] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [instructionText, setInstructionText] = useState('')
  const [instructionKind, setInstructionKind] = useState<'change' | 'question' | 'edit'>('change')
  const [instructionBusy, setInstructionBusy] = useState(false)
  const [instructionNotice, setInstructionNotice] = useState<string | null>(null)
  const [hiSeq, setHiSeq] = useState<number | null>(null)
  const [goalOpen, setGoalOpen] = useState(false)
  const lastSeq = useRef(0)
  const [motionPaused, setMotionPaused] = useState(false)
  // An explicit ?tab= wins; otherwise a finished run opens on its report once, on first load.
  const tabDecided = useRef(new URLSearchParams(window.location.search).has('tab'))

  const reload = useCallback(async () => {
    try {
      const d = await api.run(runId)
      setRun(d)
      if (!tabDecided.current) {
        tabDecided.current = true
        if (TERMINAL.includes(d.status) && d.final_report) setTab('report')
      }
      if (d.artifacts.length) {
        const latest = [...d.artifacts].filter((a) => a.artifact_id !== 'final-report.md').sort((a, b) => b.revision - a.revision)
        const pick = latest.find((a) => a.media_type.includes('html')) || latest[0] || d.artifacts[0]
        // Only the first load chooses a file. A functional update keeps the reader's later choice even when this
        // callback was captured by the event stream before that choice was made.
        if (pick) setSelArt((current) => current ?? { id: pick.artifact_id, rev: pick.revision })
      }
    } catch (e) { setErr(String(e)) }
  }, [runId])

  const reloadProjections = useCallback(async () => {
    try {
      const [c, t] = await Promise.all([api.chat(runId), api.timeline(runId, true)])
      setChat(c); setTimeline(t)
    } catch (e) { setErr(String(e)) }
  }, [runId])

  useEffect(() => {
    let es: EventSource | null = null
    let alive = true
    ;(async () => {
      await reload()
      const evs = await api.events(runId, 0)
      if (!alive) return
      setEvents(evs)
      lastSeq.current = evs.length ? evs[evs.length - 1].seq : 0
      await reloadProjections()
      es = new EventSource(`/api/runs/${runId}/stream?after_seq=${lastSeq.current}`)
      const onEvent = (e: MessageEvent) => {
        const ev: Event = JSON.parse(e.data)
        if (ev.seq <= lastSeq.current) return
        lastSeq.current = ev.seq
        setEvents((prev) => [...prev, ev])
        if (/^(task|run|artifact\.(published|adopted)|approval|plan|report|instruction)/.test(ev.type)) reload()
        if (ev.type === 'message.sent' || ev.type.startsWith('run.') || ev.type === 'check.completed' || ev.type === 'review.submitted' || ev.type === 'instruction.received') reloadProjections()
        else setTimeline((prev) => [...prev, { seq: ev.seq, event_id: ev.event_id, recorded_at: ev.recorded_at, actor_id: ev.actor_id, actor_kind: ev.actor_kind, task_id: ev.task_id, causation_id: ev.causation_id, type: ev.type, title: ev.type, detail: '' }])
      }
      // named SSE events: subscribe to every type we know plus the generic 'message'
      const types = ['run.created', 'run.started', 'run.completed', 'run.partial', 'run.failed', 'run.cancelled', 'run.interrupted', 'run.resumed', 'run.forked', 'run.blocked', 'config.resolved',
        'plan.proposed', 'plan.rejected', 'plan.accepted', 'task.created', 'task.ready', 'task.started', 'task.waiting', 'task.blocked', 'task.review_pending', 'task.accepted', 'task.partial', 'task.failed',
        'task.cancelled', 'task.interrupted', 'task.updated', 'model.called', 'model.failed', 'tool.called', 'message.sent', 'message.read', 'artifact.published', 'artifact.read', 'check.completed',
        'review.submitted', 'approval.requested', 'approval.resolved', 'blocker.reported', 'checkpoint.saved', 'report.generated', 'budget.exceeded', 'policy.denied', 'instruction.received', 'artifact.adopted']
      for (const t of types) es.addEventListener(t, onEvent as EventListener)
      es.addEventListener('end', () => { es?.close(); reload(); reloadProjections() })
      es.onerror = () => { /* EventSource reconnects with Last-Event-ID */ }
    })().catch(e => { if (alive) setErr(String(e)); es?.close() })
    return () => { alive = false; es?.close() }
  }, [runId, reload, reloadProjections])

  const agents = run?.config_snapshot?.agents || {}
  const tz = undefined
  const live = run ? !TERMINAL.includes(run.status) && run.status !== 'blocked' : false
  const artifactsById = useMemo(() => {
    const m = new Map<string, Artifact[]>()
    for (const a of run?.artifacts || []) { const l = m.get(a.artifact_id) || []; l.push(a); m.set(a.artifact_id, l) }
    for (const l of m.values()) l.sort((a, b) => a.revision - b.revision)
    return m
  }, [run])

  const act = async (fn: () => Promise<unknown>) => { setErr(null); try { await fn(); await reload() } catch (e) { setErr(String(e)) } }
  const syncAfterInstruction = useCallback(async () => {
    const fresh = await api.events(runId, lastSeq.current)
    if (fresh.length) {
      lastSeq.current = fresh[fresh.length - 1].seq
      setEvents((prev) => {
        const known = new Set(prev.map((event) => event.event_id))
        return [...prev, ...fresh.filter((event) => !known.has(event.event_id))]
      })
    }
    await Promise.all([reload(), reloadProjections()])
  }, [runId, reload, reloadProjections])
  const doFork = async () => {
    if (run?.access && !run.access.can_override) {
      await act(async () => { const child = await api.fork(runId, {}); nav(`/runs/${child.run_id}`) })
      return
    }
    const agentIds = Object.keys(agents)
    const who = window.prompt(`どの Bot のモデルを変えて分岐しますか？ (${agentIds.join(', ')}) 空欄なら設定変更なしで再実行`, 'builder')
    if (who === null) return
    const overrides: Record<string, unknown> = { rerun_tasks: [] }
    if (who.trim()) {
      const model = window.prompt(`${who} のモデル ID`, agents[who]?.model || '')
      if (model === null) return
      overrides.agents = { [who]: { model } }
      overrides.rerun_tasks = (run?.tasks || []).filter((t) => t.spec.owner === who).map((t) => t.spec.id)
    }
    await act(async () => { const child = await api.fork(runId, overrides); nav(`/runs/${child.run_id}`) })
  }

  if (!run) return <p className="muted">{err || tr('読み込み中…')}</p>
  const canWrite = run.access?.can_write !== false
  const pendingApprovals = run.approvals.filter((a) => a.status === 'pending')
  return (
    <div className={motionPaused ? 'run-view motion-paused' : 'run-view'}>
      <div className="runhead">
        <div>
          <div className="row">
            {['running', 'planning'].includes(run.status) && <Orb state="thinking" size={44} title={tr("モデル呼出中")} />}
            <span className={'tag status-' + run.status}>{run.status === 'queued' ? tr('実行待ち') : run.status}</span>
            {run.provider_kind === 'fake' && <span className="tag fake">{tr("FAKE PROVIDER — 実 LLM ではありません")}</span>}
            {run.parent_run_id && <span className="tag">fork of <Link to={`/runs/${run.parent_run_id}`} nav={nav}>{run.parent_run_id.slice(0, 16)}</Link> @seq {run.fork_from_seq}</span>}
          </div>
          <h1 style={{ marginTop: 6 }} className={goalOpen ? undefined : 'goal-clamp'} title={goalOpen ? undefined : run.goal}>{run.goal}</h1>
          {run.goal.length > 60 && <button type="button" className="goal-toggle" aria-expanded={goalOpen} onClick={() => setGoalOpen(!goalOpen)}>{goalOpen ? tr('依頼文をたたむ') : tr('依頼文の全文を表示')}</button>}
          <div className="chips">
            <span className="tag">{run.usage.model_calls} model calls</span>
            <span className="tag">{run.usage.tool_calls} tool calls</span>
            <span className="tag">{money(run.usage.cost_usd)}{run.usage.reserved_usd > 0 ? ` (+${money(run.usage.reserved_usd)} reserved)` : ''}</span>
            <span className="tag">{run.usage.input_tokens + run.usage.output_tokens} tokens</span>
            <span className="tag">{Math.round(run.usage.wall_seconds)}s</span>
            <span className="tag">seq {run.last_seq}</span>
          </div>
          {run.plan?.assumptions?.length ? (
            <details className="assumptions" title={tr("Master が記録した前提")}>
              <summary>{tr('前提')} ({run.plan.assumptions.length})</summary>
              <ul>{run.plan.assumptions.map((a, i) => <li key={i}>{a}</li>)}</ul>
            </details>
          ) : null}
          {run.blocked_reason && <p className="err small" style={{ marginTop: 6 }}>{run.blocked_reason}</p>}
          {run.status === 'queued' && <p className="muted small">{tr('実行枠が空き次第、開始します。')}</p>}
        </div>
        <div className="stack" style={{ alignItems: 'flex-end' }}>
          <div className="row">
            {canWrite && live && <button className="btn ghost" onClick={() => act(() => api.cancel(runId))}>{tr("停止")}</button>}
            {canWrite && ['interrupted', 'approval_required', 'failed', 'partial', 'cancelled'].includes(run.status) && <button className="btn" onClick={() => act(() => api.resume(runId))}>{tr("再開")}</button>}
            {canWrite && run.plan && <button className="btn ghost" onClick={doFork}>{tr("分岐して再実行")}</button>}
            <a className="btn ghost" href={`/api/runs/${runId}/export?fmt=jsonl`}>JSONL</a>
            <button type="button" className="btn ghost" aria-pressed={motionPaused} onClick={() => setMotionPaused(!motionPaused)}>{getLang() === 'en' ? 'Pause animation' : '動きを止める'}</button>
          </div>
          {pendingApprovals.length > 0 && <button className="btn signal" onClick={() => setTab('approvals')}>承認待ち {pendingApprovals.length} 件</button>}
          {err && <span className="err small">{err}</span>}
        </div>
      </div>

      <div className="work work-chat-first">
        <section className="pane chat-pane chat-main">
          <header>
            <div className="tabs">
              {(['chat', 'timeline', 'report', 'approvals'] as Tab[]).map((t) => (
                <button key={t} aria-pressed={tab === t} className={tab === t ? 'active' : ''} onClick={() => setTab(t)}>
                  {{ chat: tr('チームチャット'), timeline: tr('時系列'), report: tr('最終報告'), approvals: tr('承認') }[t]}{t === 'approvals' && pendingApprovals.length ? ` (${pendingApprovals.length})` : ''}
                </button>
              ))}
            </div>
            {tab === 'timeline' && <label className="small muted" style={{ marginLeft: 'auto' }}><input type="checkbox" checked={showTools} onChange={(e) => setShowTools(e.target.checked)} /> {tr("ツール呼出も表示")}</label>}
          </header>
          <div className="body">
            {tab === 'chat' && <>
              <Chat chat={chat} agents={agents} tz={tz} ended={TERMINAL.includes(run.status)} onJump={(seq) => { setTab('timeline'); setHiSeq(seq) }} />
              <InstructionComposer runId={runId} run={run} events={events} canWrite={canWrite} instructionText={instructionText}
                setInstructionText={setInstructionText} instructionKind={instructionKind} setInstructionKind={setInstructionKind}
                busy={instructionBusy} setBusy={setInstructionBusy} notice={instructionNotice} setNotice={setInstructionNotice} onSent={syncAfterInstruction} />
            </>}
            {tab === 'timeline' && <Timeline items={timeline.filter((i) => showTools || !['tool.called', 'message.read', 'artifact.read', 'checkpoint.saved', 'model.called'].includes(i.type))} tz={tz} hiSeq={hiSeq} selTask={selTask} />}
            {tab === 'report' && <Report run={run} />}
            {tab === 'approvals' && <Approvals approvals={run.approvals} onResolved={reload} readOnly={!canWrite} />}
          </div>
        </section>
          <aside className="chat-side" aria-label={tr('実行の補助情報')}>
          <TeamPane run={run} agents={agents} selTask={selTask} setSelTask={setSelTask} onJump={(seq) => { setTab('timeline'); setHiSeq(seq) }} />
          <ArtifactPane run={run} artifactsById={artifactsById} selections={run.artifact_selection || {}} sel={selArt} setSel={setSelArt} events={events} canWrite={canWrite}
            onChanged={reload} onJump={(seq) => { setTab('timeline'); setHiSeq(seq) }} />
        </aside>
      </div>
    </div>
  )
}

function TeamPane({ run, agents, selTask, setSelTask, onJump }: { run: RunDetail; agents: Record<string, any>; selTask: string | null; setSelTask: (t: string | null) => void; onJump: (seq: number) => void }) {
  const byOwner = new Map<string, TaskState[]>()
  for (const t of run.tasks) { const l = byOwner.get(t.spec.owner) || []; l.push(t); byOwner.set(t.spec.owner, l) }
  const ids = Object.keys(agents).filter((id) => agents[id].enabled)
  return (
    <section className="pane">
      <header><h3>{tr("チーム")}</h3><span className="muted small" style={{ marginLeft: 'auto' }}>{run.plan ? `${run.tasks.length} tasks` : run.status === 'planning' ? 'Master が計画中…' : ''}</span></header>
      <div className="body">
        {ids.map((id) => {
          const a = agents[id]
          const tasks = byOwner.get(id) || []
          const used = run.plan?.agents.includes(id)
          const botState = botActivity(tasks, run.status, id, a.role, a.enabled)
          return (
            <div className={'agent bot-agent state-' + botState} key={id} style={{ opacity: run.plan && !used ? 0.5 : 1 }}>
              <BotCharacter id={id} role={a.role} emoji={a.emoji} name={a.display_name} state={botState} size="card" />
              <div className="agent-content">
              <div className="name">{a.display_name || id} <span className="tag">{a.role}</span>{a.prompt_mode === 'user_locked' && <span className="tag" title={tr("手動固定プロンプト")}>locked</span>}</div>
              <div className="bot-activity-label" role="status">{botStateLabel(botState, getLang())}</div>
              <details className="bot-model-details"><summary>{getLang() === 'en' ? 'Model details' : 'モデルの詳細'}</summary><div className="model">{a.model} · {a.connection_id}/{a.driver} · prompt {a.system_prompt_sha256.slice(0, 8)}</div></details>
              {tasks.map((t) => (
                <div key={t.spec.id} className={'task' + (selTask === t.spec.id ? ' active' : '')}>
                  <button type="button" className="task-select" aria-expanded={selTask === t.spec.id} onClick={() => setSelTask(selTask === t.spec.id ? null : t.spec.id)}>
                  <span className="row" style={{ gap: 6 }}>
                    <b className="mono">{t.spec.id}</b>
                    <span className={'tag status-' + t.status}>{t.status}</span>
                    {t.attempt > 0 && <span className="tag">attempt {t.attempt}</span>}
                  </span>
                  <span className="obj">{t.spec.objective}</span>
                  </button>
                  {selTask === t.spec.id && (
                    <div className="small" style={{ marginTop: 6 }}>
                      {t.spec.depends_on.length > 0 && <div className="muted">depends: {t.spec.depends_on.join(', ')}</div>}
                      {t.spec.output_paths.length > 0 && <div className="muted">outputs: {t.spec.output_paths.join(', ')}</div>}
                      <ul style={{ margin: '4px 0', paddingLeft: 16 }}>
                        {t.spec.acceptance.map((c) => {
                          const r = t.review?.results.find((x) => x.acceptance_id === c.id)
                          return <li key={c.id}><span className={'tag ' + (r ? r.status : '')}>{c.id} {r ? r.status : c.check_kind}</span> {c.description}{r?.note ? <span className="muted"> — {r.note}</span> : null}</li>
                        })}
                      </ul>
                      {t.result?.summary && <div><b>{tr("結果:")}</b> {t.result.summary}</div>}
                      {t.result?.unverified?.length ? <div className="muted">未検証: {t.result.unverified.join(' / ')}</div> : null}
                      {t.blocked_reason && <div className="err">{t.blocked_reason}</div>}
                      <button className="btn sm ghost" style={{ marginTop: 4 }} onClick={(e) => { e.stopPropagation(); onJump(0) }}>{tr("時系列で見る")}</button>
                    </div>
                  )}
                </div>
              ))}
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}

function ArtifactPane({ run, artifactsById, selections, sel, setSel, events, canWrite, onChanged, onJump }: { run: RunDetail; artifactsById: Map<string, Artifact[]>; selections: Record<string, ArtifactSelection>; sel: { id: string; rev: number } | null; setSel: (s: { id: string; rev: number }) => void; events: Event[]; canWrite: boolean; onChanged: () => Promise<void>; onJump: (seq: number) => void }) {
  const [detail, setDetail] = useState<any>(null)
  const [diffFrom, setDiffFrom] = useState<number | null>(null)
  const [diffText, setDiffText] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  useEffect(() => { if (sel) api.artifact(run.run_id, sel.id, sel.rev).then(setDetail).catch(() => setDetail(null)) }, [sel, run.run_id, run.last_seq])
  useEffect(() => { setDiffText(null); setDiffFrom(null); setNotice(null) }, [sel?.id, sel?.rev])
  const revs = sel ? artifactsById.get(sel.id) || [] : []
  const cur = revs.find((r) => r.revision === sel?.rev)
  const adopted = sel ? selections[sel.id] : undefined
  const isHtml = !!cur && cur.media_type.includes('html')
  const related = sel ? events.filter((e) => (e.type === 'artifact.published' && e.payload.artifact_id === sel.id && e.payload.revision === sel.rev)
    || (e.type === 'check.completed' && e.payload.target?.artifact_id === sel.id && e.payload.target?.revision === sel.rev)
    || (e.type === 'review.submitted' && (e.payload.target_artifacts || []).some((a: any) => a.artifact_id === sel.id && a.revision === sel.rev))
    || (e.type === 'message.sent' && (e.payload.artifact_refs || []).some((a: any) => a.artifact_id === sel.id && a.revision === sel.rev))) : []
  return (
    <section className="pane">
      <header>
        <h3>{tr("成果物")}</h3>
        <span className="muted small" style={{ marginLeft: 'auto' }}>{artifactsById.size} files</span>
        <a className="btn sm ghost" href={`/api/runs/${run.run_id}/export?fmt=zip`}>{tr('まとめて取得')}</a>
      </header>
      <div className="body stack">
        <div className="art-list">
          {[...artifactsById.entries()].map(([id, list]) => {
            const last = list[list.length - 1]
            return (
              <button type="button" key={id} aria-pressed={sel?.id === id} className={'art' + (sel?.id === id ? ' active' : '')} onClick={() => setSel({ id, rev: last.revision })}>
                <span className="path">{last.logical_path}</span>
                <span className="tag">r{last.revision}</span>
                <span className="muted small">{last.agent_id}{last.task_id ? `/${last.task_id}` : ''}</span>
              </button>
            )
          })}
          {artifactsById.size === 0 && <p className="muted small">{tr("まだ成果物は公開されていません。")}</p>}
        </div>
        {cur && (
          <>
            <div className="row">
              <div className="revs">{revs.map((r) => <button key={r.revision} className={r.revision === sel?.rev ? 'active' : ''} onClick={() => setSel({ id: r.artifact_id, rev: r.revision })}>r{r.revision}</button>)}</div>
              <span className="mono muted small">sha256 {cur.sha256.slice(0, 16)}… · {cur.media_type} · {cur.size}B · {fmtTime(cur.created_at)}</span>
              <a className="btn sm ghost" href={api.artifactRawUrl(run.run_id, cur.artifact_id, cur.revision)} target="_blank" rel="noreferrer">raw</a>
              {canWrite && adopted?.revision !== cur.revision && <button className="btn sm signal" disabled={busy} onClick={async () => {
                setBusy(true); setNotice(null)
                try { await api.adoptArtifact(run.run_id, cur.artifact_id, { revision: cur.revision, expected_selected_revision: adopted?.revision }); setNotice(tr('この版を採用しました。')); await onChanged() }
                catch (e) { setNotice(String(e)) } finally { setBusy(false) }
              }}>{busy ? tr('採用中…') : tr('この版を採用')}</button>}
              {adopted?.revision === cur.revision && <span className="tag status-completed">{tr('採用版')}</span>}
            </div>
            {revs.length > 1 && <div className="artifact-diff-controls">
              <select className="input" value={diffFrom ?? ''} onChange={(e) => setDiffFrom(e.target.value ? Number(e.target.value) : null)} aria-label={tr('比較元の版')}>
                <option value="">{tr('比較する版を選択')}</option>
                {revs.filter((r) => r.revision !== cur.revision).map((r) => <option key={r.revision} value={r.revision}>r{r.revision}</option>)}
              </select>
              <button className="btn sm ghost" disabled={!diffFrom} onClick={async () => { if (!diffFrom || !cur) return; setBusy(true); try { const d = await api.artifactDiff(run.run_id, cur.artifact_id, diffFrom, cur.revision); setDiffText(d.supported ? d.diff || tr('変更はありません。') : d.reason || tr('この形式の差分には対応していません。')) } catch (e) { setDiffText(String(e)) } finally { setBusy(false) } }}>{tr('差分を見る')}</button>
            </div>}
            {notice && <p className="small" role="status">{notice}</p>}
            {diffText !== null && <pre className="artifact-diff" aria-label={tr('成果物の差分')}>{diffText}</pre>}
            <div className="preview">
              {isHtml ? <iframe title={cur.logical_path} sandbox="" src={api.artifactRawUrl(run.run_id, cur.artifact_id, cur.revision)} />
                : <pre>{detail?.text ?? '(binary)'}</pre>}
            </div>
            <div className="small">
              <h3>{tr("この revision の経緯")}</h3>
              {related.length === 0 && <span className="muted">{tr("関連イベントなし")}</span>}
              {related.map((e) => (
                <div key={e.event_id} className="row" style={{ gap: 6, padding: '3px 0' }}>
                  <span className="mono muted">#{e.seq}</span>
                  <b>{e.actor_id}</b>
                  <span>{e.type === 'artifact.published' ? '公開' : e.type === 'check.completed' ? `検証 ${e.payload.kind} → ${e.payload.result?.status}` : e.type === 'review.submitted' ? `レビュー: ${(e.payload.results || []).map((r: any) => `${r.acceptance_id}=${r.status}`).join(', ')}` : `メッセージ → ${e.payload.to_agent_id} [${e.payload.purpose}]`}</span>
                  {e.payload.result?.problems?.length ? <span className="err">{e.payload.result.problems.join('; ')}</span> : null}
                  <button className="btn sm ghost" onClick={() => onJump(e.seq)}>{tr("→ 時系列")}</button>
                </div>
              ))}
              {cur.sources?.length ? <div className="muted">sources: {cur.sources.join(', ')}</div> : null}
            </div>
          </>
        )}
      </div>
    </section>
  )
}

function Chat({ chat, agents, tz, onJump, ended = false }: { chat: ChatMessage[]; agents: Record<string, any>; tz?: string; onJump: (seq: number) => void; ended?: boolean }) {
  const [query, setQuery] = useState('')
  const [taskFilter, setTaskFilter] = useState<string | null>(null)
  if (chat.length === 0) return (
    <div className="chat-empty">
      <div className="chat-empty-icon" aria-hidden="true">✦</div>
      <h2>{ended ? tr('Bot 間のメッセージはありませんでした') : tr('メッセージを待っています')}</h2>
      <p className="muted small">{ended ? tr("この実行では、受信箱へ配送されたメッセージはありません。作業の経緯は時系列で確認できます。") : tr("Bot 間のメッセージはまだありません。表示されるのは実際に宛先の受信箱へ配送されたメッセージだけです。")}</p>
    </div>
  )
  const taskIds = [...new Set(chat.map((m) => m.task_id).filter(Boolean))]
  const flow = chat.reduce<string[]>((ids, m) => {
    for (const id of [m.from, m.to]) if (ids[ids.length - 1] !== id) ids.push(id)
    return ids
  }, [])
  const needle = query.trim().toLocaleLowerCase()
  const visibleChat = chat.filter((m) => {
    if (taskFilter && m.task_id !== taskFilter) return false
    if (!needle) return true
    return [m.from, m.to, m.task_id, m.purpose, m.text].join(' ').toLocaleLowerCase().includes(needle)
  })
  return (
    <section className="chat-shell" aria-label={tr('チームチャット')}>
      <div className="chat-hero">
        <div className="chat-hero-title">
          <span className="chat-spark" aria-hidden="true">✦</span>
          <div>
            <span className="chat-eyebrow">{tr('実行のコミュニケーション')}</span>
            <h2>{tr('チームチャット')}</h2>
          </div>
        </div>
        <div className="chat-live"><span className="chat-live-dot" aria-hidden="true" />{tr('実メッセージ')}<b>{chat.length}</b></div>
      </div>
      <p className="chat-caption">{tr('実際に受信箱へ届いたメッセージを、担当Botごとに表示しています。')}</p>
      <div className="chat-overview">
        <div className="chat-overview-main">
          <span className="chat-section-label">{tr('協働フロー')}</span>
          <div className="chat-flow" aria-label={tr('協働フロー')}>
            {flow.map((id, index) => (
              <span className="chat-flow-segment" key={id + index}>
                {index > 0 && <span className="chat-flow-arrow" aria-hidden="true">→</span>}
                <span className={'chat-flow-node tone-' + avatarTone(id)}><BotCharacter id={id} role={agents[id]?.role} emoji={agents[id]?.emoji} state="idle" size="micro" /><b>{agents[id]?.display_name || id}</b></span>
              </span>
            ))}
          </div>
        </div>
        <div className="chat-metrics" aria-label={tr('参加Bot')}>
          <span><b>{new Set(chat.flatMap((m) => [m.from, m.to])).size}</b>{tr('参加Bot')}</span>
          <span><b>{taskIds.length}</b>{tr('作業スレッド')}</span>
        </div>
      </div>
      <div className="chat-controls" role="group" aria-label={tr('メッセージを整理')}>
        <label className="chat-search">
          <span>{tr('メッセージを検索')}</span>
          <input value={query} onChange={(e) => setQuery(e.target.value)} aria-label={tr('メッセージを検索')} />
        </label>
        <div className="chat-task-filters" role="group" aria-label={tr('作業スレッド')}>
          <button type="button" className={!taskFilter ? 'active' : ''} aria-pressed={!taskFilter} onClick={() => setTaskFilter(null)}>{tr('すべて')}</button>
          {taskIds.map((id) => <button type="button" key={id} className={taskFilter === id ? 'active' : ''} aria-pressed={taskFilter === id} onClick={() => setTaskFilter(taskFilter === id ? null : id)}>{id}</button>)}
        </div>
        <span className="chat-result-count">{visibleChat.length}/{chat.length}{tr('件表示')}</span>
      </div>
      <div className="chat-stream" role="log" aria-live="polite" aria-relevant="additions text" aria-label={tr('実行のコミュニケーション')}>
        {visibleChat.length === 0 && <div className="chat-filter-empty">{tr('該当するメッセージはありません')}</div>}
        {visibleChat.map((m, index) => {
          const agent = agents[m.from]
          return (
            <article key={m.event_id} className={'chat-card' + (index === visibleChat.length - 1 ? ' latest' : '')} aria-label={`${m.from} → ${m.to}`}>
              <BotCharacter id={m.from} role={agent?.role} emoji={agent?.emoji} name={agent?.display_name} state="idle" size="chat" />
              <div className="chat-card-main">
                <div className="chat-authorline">
                  <b>{agent?.display_name || m.from}</b>
                  {agent?.role && <span className="chat-role">{agent.role}</span>}
                  <span className="chat-time">{fmtTime(m.recorded_at, tz)}</span>
                </div>
                <div className="chat-route">
                  <span title={m.from}>{agent?.display_name || m.from}</span><span className="chat-arrow" aria-hidden="true">→</span><span title={m.to}>{agents[m.to]?.display_name || m.to}</span>
                  {m.task_id && <span className="chat-task">{m.task_id}</span>}
                </div>
                <div className="chat-bubble">
                  <div className="chat-text">{m.text}</div>
                </div>
                <div className="chat-footer">
                  <span className="chat-purpose">{m.purpose}</span>
                  {m.reply_to && <span className="chat-reply">↳ {tr('返信')} {m.reply_to.slice(0, 12)}</span>}
                  {m.artifact_refs.length > 0 && <div className="chat-artifacts">{m.artifact_refs.map((r) => <span key={r.artifact_id + r.revision} className="chat-artifact">▣ {r.artifact_id} <b>r{r.revision}</b></span>)}</div>}
                  <button className="chat-jump" onClick={() => onJump(m.seq)} aria-label={`${tr('メッセージを時系列で見る')} #${m.seq}`}>#{m.seq} <span aria-hidden="true">↗</span></button>
                </div>
              </div>
            </article>
          )
        })}
      </div>
    </section>
  )
}

function InstructionComposer({
  runId, run, events, canWrite, instructionText, setInstructionText, instructionKind, setInstructionKind,
  busy, setBusy, notice, setNotice,
  onSent,
}: {
  runId: string
  run: RunDetail
  events: Event[]
  canWrite: boolean
  instructionText: string
  setInstructionText: (value: string) => void
  instructionKind: 'change' | 'question' | 'edit'
  setInstructionKind: (value: 'change' | 'question' | 'edit') => void
  busy: boolean
  setBusy: (value: boolean) => void
  notice: string | null
  setNotice: (value: string | null) => void
  onSent: () => Promise<void>
}) {
  const [error, setError] = useState<string | null>(null)
  const history = events.filter((e) => e.type === 'instruction.received').slice(-3)
  const sendable = canWrite && ['created', 'queued', 'planning', 'running'].includes(run.status)
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const text = instructionText.trim()
    if (!text || busy || !sendable) return
    setBusy(true); setError(null); setNotice(null)
    try {
      await api.instruction(runId, { text, kind: instructionKind })
      setInstructionText('')
      setNotice(tr('指示を受信しました。'))
      await onSent()
    } catch (e) {
      setError(`${tr('指示を送信できませんでした。')} ${String(e)}`)
    } finally { setBusy(false) }
  }
  return (
    <section className="instruction-composer" aria-label={tr('人間の指示')}>
      <header>
        <span className="chat-spark" aria-hidden="true">↗</span>
        <div>
          <h3>{tr('人間の指示')}</h3>
          <p className="instruction-note">{sendable ? tr('次に開始するタスクへ引き継ぎます。実行中の計画は自動で書き換えません。') : run.status === 'blocked' || TERMINAL.includes(run.status) ? tr('再開または分岐してから指示を送ってください。') : tr('この run が進行中または開始前のときだけ送信できます。')}</p>
        </div>
      </header>
      <form onSubmit={submit}>
        <textarea className="input" maxLength={4000} placeholder={tr('指示を入力')} value={instructionText} onChange={(e) => setInstructionText(e.target.value)} disabled={!sendable || busy} />
        <div className="instruction-foot">
          <select className="input" aria-label={tr('人間の指示')} value={instructionKind} onChange={(e) => setInstructionKind(e.target.value as 'change' | 'question' | 'edit')} disabled={!sendable || busy}>
            <option value="change">{tr('変更')}</option>
            <option value="question">{tr('質問')}</option>
            <option value="edit">{tr('編集')}</option>
          </select>
          <button className="btn signal" type="submit" disabled={!sendable || busy || !instructionText.trim()}>{busy ? tr('送信中…') : tr('指示を送る')}</button>
          {notice && <span className="small" style={{ color: 'var(--ok)' }}>{notice}</span>}
          {error && <span className="err small" role="alert">{error}</span>}
        </div>
      </form>
      {history.length > 0 && <div className="instruction-history" aria-label={tr('人間の指示')}>
        {history.map((e) => <div className="instruction-history-item" key={e.event_id}><span className="mono">#{e.seq} {e.payload.kind || 'change'}</span>{String(e.payload.text || '')}</div>)}
      </div>}
    </section>
  )
}

function avatarTone(id: string) {
  let hash = 0
  for (const char of id) hash = (hash * 31 + char.charCodeAt(0)) >>> 0
  return hash % 6
}

function Timeline({ items, tz, hiSeq, selTask }: { items: TimelineItem[]; tz?: string; hiSeq: number | null; selTask: string | null }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => { if (hiSeq != null) ref.current?.querySelector(`[data-seq="${hiSeq}"]`)?.scrollIntoView({ block: 'center' }) }, [hiSeq, items.length])
  return (
    <div className="tl" ref={ref}>
      {items.filter((i) => !selTask || i.task_id === selTask || i.type.startsWith('run.')).map((i) => {
        const hi = i.seq === hiSeq ? ' hi' : ''
        return [
          <div key={i.seq + 'a'} className={'seq' + hi} data-seq={i.seq}>{i.seq}</div>,
          <div key={i.seq + 'b'} className={'time' + hi}>{fmtTime(i.recorded_at, tz)}</div>,
          <div key={i.seq + 'c'} className={'t' + hi}><span className="actor">{i.actor_id}</span><span>{i.title}</span>{i.task_id && <span className="mono muted">{i.task_id}</span>}<span className="detail">{i.detail}</span></div>,
        ]
      })}
    </div>
  )
}

function Report({ run }: { run: RunDetail }) {
  const r = run.final_report
  if (!r) return <p className="muted small">{TERMINAL.includes(run.status) ? '報告はありません。' : tr('実行完了後に、成果物・検証・未解決・費用・経緯参照をまとめた報告が生成されます。')}</p>
  const n = r.narrative
  const ev = r.evidence
  return (
    <div className="report small">
      <div className="row"><span className={'tag status-' + r.status}>{r.status}</span>{r.reason && <span className="err">{r.reason}</span>}<span className="muted">{n ? `要約: ${n.author}` : tr('要約: 生成なし（証拠のみ）')}</span></div>
      {n?.summary && <><h2>{tr("要約")}</h2><Markdown text={n.summary} className="prose" /></>}
      <h2>{tr("成果物")}</h2>
      <ul>{r.deliverables.map((d: any) => <li key={d.artifact_id + d.revision}><code>{d.logical_path}</code> r{d.revision} <span className="muted">sha {d.sha256.slice(0, 12)} · {d.by}/{d.task_id}</span></li>)}</ul>
      <h2>{tr("検証済み")}</h2>
      <ul>
        {ev.checks.map((c: any) => <li key={c.seq}>check <code>{c.kind}</code> on {c.target?.artifact_id} r{c.target?.revision} → <span className={'tag ' + c.status}>{c.status}</span> <span className="muted">#{c.seq}</span></li>)}
        {ev.reviews.map((rv: any) => <li key={rv.seq}>review of {rv.target_task_id} by {rv.by}: {rv.results.map((x: any) => <span key={x.acceptance_id} className={'tag ' + x.status} style={{ marginRight: 4 }}>{x.acceptance_id} {x.status}</span>)} <span className="muted">#{rv.seq}</span></li>)}
        {n?.verified?.map((v: string, i: number) => <li key={i}>{v}</li>)}
      </ul>
      <h2>{tr("未解決・承認待ち")}</h2>
      <ul>
        {ev.failures.map((f: any) => <li key={f.seq}>{f.type} {f.task_id} — {f.reason} <span className="muted">#{f.seq}</span></li>)}
        {ev.blockers.map((b: any) => <li key={b.seq}>{b.actor}: {b.reason} — 必要: {b.needed}</li>)}
        {n?.unresolved?.map((u: string, i: number) => <li key={i}>{u}</li>)}
        {ev.failures.length + ev.blockers.length === 0 && !n?.unresolved?.length && <li className="muted">{tr("なし")}</li>}
      </ul>
      {n?.next_steps?.length ? <><h2>{tr("次の一手")}</h2><ul>{n.next_steps.map((s: string, i: number) => <li key={i}>{s}</li>)}</ul></> : null}
      <h2>{tr("時間・費用")}</h2>
      <dl className="kv">
        <dt>model calls</dt><dd>{r.usage.model_calls}</dd>
        <dt>cost</dt><dd>{money(r.usage.cost_usd)}</dd>
        <dt>wall</dt><dd>{Math.round(r.usage.wall_seconds)}s</dd>
        <dt>by agent</dt><dd>{Object.entries(ev.model_usage_by_agent).map(([k, v]: any) => `${k}: ${v.calls} calls / ${money(v.cost_usd)} (reported: ${v.models_reported.join(', ') || 'unknown'})`).join(' · ')}</dd>
        <dt>provider</dt><dd>{ev.run.provider_kind}</dd>
      </dl>
      <p><a href={`/api/runs/${run.run_id}/export?fmt=md`} target="_blank" rel="noreferrer">{tr("final-report.md を開く")}</a></p>
    </div>
  )
}

function Approvals({ approvals, onResolved, readOnly = false }: { approvals: Approval[]; onResolved: () => void; readOnly?: boolean }) {
  const [err, setErr] = useState<string | null>(null)
  const resolve = async (a: Approval, decision: string) => {
    setErr(null)
    try { await api.resolveApproval(a.approval_id, { decision, expected_hash: a.payload_hash, nonce: a.nonce }); onResolved() } catch (e) { setErr(String(e)) }
  }
  if (approvals.length === 0) return <p className="muted small">{tr("承認要求はありません。外部への投稿・送信・支払い・本番変更は、承認されるまで実行されません。")}</p>
  return (
    <div className="stack">
      {err && <p className="err">{err}</p>}
      {approvals.map((a) => (
        <div key={a.approval_id} className="approval">
          <div className="row"><b>{a.agent_id}</b> {tr("が")} <code>{a.action}</code> {tr("の承認を要求")} <span className={'tag status-' + (a.status === 'pending' ? 'approval_required' : a.status === 'approved' ? 'completed' : 'failed')}>{a.status}</span></div>
          <div>{String(a.payload.description ?? '')}</div>
          <pre>{JSON.stringify(a.payload.payload, null, 1)}</pre>
          <div className="mono muted small">hash {a.payload_hash.slice(0, 16)}… · 期限 {fmtTime(a.expires_at)}{a.payload.estimated_cost_usd != null ? ` · 見積 $${a.payload.estimated_cost_usd}` : ''}</div>
          {!readOnly && a.status === 'pending' && <div className="row" style={{ marginTop: 8 }}>
            <button className="btn signal sm" onClick={() => resolve(a, 'approve')}>{tr("承認")}</button>
            <button className="btn ghost sm" onClick={() => resolve(a, 'reject')}>{tr("却下")}</button>
          </div>}
        </div>
      ))}
    </div>
  )
}

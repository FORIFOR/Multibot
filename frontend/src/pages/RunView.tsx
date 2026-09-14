import { t as tr } from '../lib/i18n'
import Orb from '../components/Orb'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, fmtTime, money, TERMINAL, type Approval, type Artifact, type ChatMessage, type Event, type RunDetail, type TaskState, type TimelineItem } from '../lib/api'
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
  const [hiSeq, setHiSeq] = useState<number | null>(null)
  const lastSeq = useRef(0)

  const reload = useCallback(async () => {
    try {
      const d = await api.run(runId)
      setRun(d)
      if (!selArt && d.artifacts.length) {
        const latest = [...d.artifacts].filter((a) => a.artifact_id !== 'final-report.md').sort((a, b) => b.revision - a.revision)
        const pick = latest.find((a) => a.media_type.includes('html')) || latest[0] || d.artifacts[0]
        if (pick) setSelArt({ id: pick.artifact_id, rev: pick.revision })
      }
    } catch (e) { setErr(String(e)) }
  }, [runId, selArt])

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
        if (/^(task|run|artifact\.published|approval|plan|report)/.test(ev.type)) reload()
        if (ev.type === 'message.sent' || ev.type.startsWith('run.') || ev.type === 'check.completed' || ev.type === 'review.submitted') reloadProjections()
        else setTimeline((prev) => [...prev, { seq: ev.seq, event_id: ev.event_id, recorded_at: ev.recorded_at, actor_id: ev.actor_id, actor_kind: ev.actor_kind, task_id: ev.task_id, causation_id: ev.causation_id, type: ev.type, title: ev.type, detail: '' }])
      }
      // named SSE events: subscribe to every type we know plus the generic 'message'
      const types = ['run.created', 'run.started', 'run.completed', 'run.partial', 'run.failed', 'run.cancelled', 'run.interrupted', 'run.resumed', 'run.forked', 'run.blocked', 'config.resolved',
        'plan.proposed', 'plan.rejected', 'plan.accepted', 'task.created', 'task.ready', 'task.started', 'task.waiting', 'task.blocked', 'task.review_pending', 'task.accepted', 'task.partial', 'task.failed',
        'task.cancelled', 'task.interrupted', 'task.updated', 'model.called', 'model.failed', 'tool.called', 'message.sent', 'message.read', 'artifact.published', 'artifact.read', 'check.completed',
        'review.submitted', 'approval.requested', 'approval.resolved', 'blocker.reported', 'checkpoint.saved', 'report.generated', 'budget.exceeded', 'policy.denied']
      for (const t of types) es.addEventListener(t, onEvent as EventListener)
      es.addEventListener('end', () => { es?.close(); reload(); reloadProjections() })
      es.onerror = () => { /* EventSource reconnects with Last-Event-ID */ }
    })().catch(e => { if (alive) setErr(String(e)); es?.close() })
    return () => { alive = false; es?.close() }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId])

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
    <div>
      <div className="runhead">
        <div>
          <div className="row">
            {['running', 'planning'].includes(run.status) && <Orb state="thinking" size={44} title={tr("モデル呼出中")} />}
            <span className={'tag status-' + run.status}>{run.status === 'queued' ? tr('実行待ち') : run.status}</span>
            {run.provider_kind === 'fake' && <span className="tag fake">{tr("FAKE PROVIDER — 実 LLM ではありません")}</span>}
            {run.parent_run_id && <span className="tag">fork of <Link to={`/runs/${run.parent_run_id}`} nav={nav}>{run.parent_run_id.slice(0, 16)}</Link> @seq {run.fork_from_seq}</span>}
          </div>
          <h1 style={{ marginTop: 6 }}>{run.goal}</h1>
          <div className="chips">
            <span className="tag">{run.usage.model_calls} model calls</span>
            <span className="tag">{run.usage.tool_calls} tool calls</span>
            <span className="tag">{money(run.usage.cost_usd)}{run.usage.reserved_usd > 0 ? ` (+${money(run.usage.reserved_usd)} reserved)` : ''}</span>
            <span className="tag">{run.usage.input_tokens + run.usage.output_tokens} tokens</span>
            <span className="tag">{Math.round(run.usage.wall_seconds)}s</span>
            <span className="tag">seq {run.last_seq}</span>
            {run.plan?.assumptions?.map((a, i) => <span key={i} className="tag" title={tr("Master が記録した前提")}>前提: {a}</span>)}
          </div>
          {run.blocked_reason && <p className="err small" style={{ marginTop: 6 }}>{run.blocked_reason}</p>}
          {run.status === 'queued' && <p className="muted small">{tr('実行枠が空き次第、開始します。')}</p>}
        </div>
        <div className="stack" style={{ alignItems: 'flex-end' }}>
          <div className="row">
            {canWrite && live && <button className="btn ghost" onClick={() => act(() => api.cancel(runId))}>{tr("停止")}</button>}
            {canWrite && ['interrupted', 'approval_required', 'failed', 'partial', 'cancelled'].includes(run.status) && <button className="btn" onClick={() => act(() => api.resume(runId))}>{tr("再開")}</button>}
            {canWrite && run.plan && <button className="btn ghost" onClick={doFork}>{tr("分岐して再実行")}</button>}
            <a className="btn ghost" href={`/api/runs/${runId}/export?fmt=jsonl`}>JSONL</a>
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
                <button key={t} className={tab === t ? 'active' : ''} onClick={() => setTab(t)}>
                  {{ chat: tr('チームチャット'), timeline: tr('時系列'), report: tr('最終報告'), approvals: tr('承認') }[t]}{t === 'approvals' && pendingApprovals.length ? ` (${pendingApprovals.length})` : ''}
                </button>
              ))}
            </div>
            {tab === 'timeline' && <label className="small muted" style={{ marginLeft: 'auto' }}><input type="checkbox" checked={showTools} onChange={(e) => setShowTools(e.target.checked)} /> {tr("ツール呼出も表示")}</label>}
          </header>
          <div className="body">
            {tab === 'chat' && <Chat chat={chat} agents={agents} tz={tz} onJump={(seq) => { setTab('timeline'); setHiSeq(seq) }} />}
            {tab === 'timeline' && <Timeline items={timeline.filter((i) => showTools || !['tool.called', 'message.read', 'artifact.read', 'checkpoint.saved', 'model.called'].includes(i.type))} tz={tz} hiSeq={hiSeq} selTask={selTask} />}
            {tab === 'report' && <Report run={run} />}
            {tab === 'approvals' && <Approvals approvals={run.approvals} onResolved={reload} readOnly={!canWrite} />}
          </div>
        </section>
        <aside className="chat-side" aria-label={tr('実行の補助情報')}>
          <TeamPane run={run} agents={agents} selTask={selTask} setSelTask={setSelTask} onJump={(seq) => { setTab('timeline'); setHiSeq(seq) }} />
          <ArtifactPane run={run} artifactsById={artifactsById} sel={selArt} setSel={setSelArt} events={events} onJump={(seq) => { setTab('timeline'); setHiSeq(seq) }} />
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
          return (
            <div className="agent" key={id} style={{ opacity: run.plan && !used ? 0.5 : 1 }}>
              <div className="name">{id} <span className="tag">{a.role}</span>{a.prompt_mode === 'user_locked' && <span className="tag" title={tr("手動固定プロンプト")}>locked</span>}</div>
              <div className="model">{a.model} · {a.connection_id}/{a.driver} · prompt {a.system_prompt_sha256.slice(0, 8)}</div>
              {tasks.map((t) => (
                <div key={t.spec.id} className={'task' + (selTask === t.spec.id ? ' active' : '')} onClick={() => setSelTask(selTask === t.spec.id ? null : t.spec.id)}>
                  <div className="row" style={{ gap: 6 }}>
                    <b className="mono">{t.spec.id}</b>
                    <span className={'tag status-' + t.status}>{t.status}</span>
                    {t.attempt > 0 && <span className="tag">attempt {t.attempt}</span>}
                  </div>
                  <div className="obj">{t.spec.objective}</div>
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
          )
        })}
      </div>
    </section>
  )
}

function ArtifactPane({ run, artifactsById, sel, setSel, events, onJump }: { run: RunDetail; artifactsById: Map<string, Artifact[]>; sel: { id: string; rev: number } | null; setSel: (s: { id: string; rev: number }) => void; events: Event[]; onJump: (seq: number) => void }) {
  const [detail, setDetail] = useState<any>(null)
  useEffect(() => { if (sel) api.artifact(run.run_id, sel.id, sel.rev).then(setDetail).catch(() => setDetail(null)) }, [sel, run.run_id, run.last_seq])
  const revs = sel ? artifactsById.get(sel.id) || [] : []
  const cur = revs.find((r) => r.revision === sel?.rev)
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
      </header>
      <div className="body stack">
        <div className="art-list">
          {[...artifactsById.entries()].map(([id, list]) => {
            const last = list[list.length - 1]
            return (
              <div key={id} className={'art' + (sel?.id === id ? ' active' : '')} onClick={() => setSel({ id, rev: last.revision })}>
                <span className="path">{last.logical_path}</span>
                <span className="tag">r{last.revision}</span>
                <span className="muted small">{last.agent_id}{last.task_id ? `/${last.task_id}` : ''}</span>
              </div>
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
            </div>
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

function Chat({ chat, agents, tz, onJump }: { chat: ChatMessage[]; agents: Record<string, any>; tz?: string; onJump: (seq: number) => void }) {
  if (chat.length === 0) return (
    <div className="chat-empty">
      <div className="chat-empty-icon" aria-hidden="true">✦</div>
      <h2>{tr('メッセージを待っています')}</h2>
      <p className="muted small">{tr("Bot 間のメッセージはまだありません。表示されるのは実際に宛先の受信箱へ配送されたメッセージだけです。")}</p>
    </div>
  )
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
      <div className="chat-stream" role="log" aria-live="polite" aria-relevant="additions text" aria-label={tr('実行のコミュニケーション')}>
        {chat.map((m, index) => {
          const agent = agents[m.from]
          const tone = avatarTone(m.from)
          return (
            <article key={m.event_id} className={'chat-card' + (index === chat.length - 1 ? ' latest' : '')} aria-label={`${m.from} → ${m.to}`}>
              <div className={'chat-avatar tone-' + tone} aria-hidden="true">{initials(m.from)}</div>
              <div className="chat-card-main">
                <div className="chat-authorline">
                  <b>{m.from}</b>
                  {agent?.role && <span className="chat-role">{agent.role}</span>}
                  <span className="chat-time">{fmtTime(m.recorded_at, tz)}</span>
                </div>
                <div className="chat-route">
                  <span>{m.from}</span><span className="chat-arrow" aria-hidden="true">→</span><span>{m.to}</span>
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

function initials(id: string) {
  const words = id.replace(/[-_]/g, ' ').trim().split(/\s+/).filter(Boolean)
  return (words.length > 1 ? words.slice(0, 2).map((w) => w[0]) : [id.slice(0, 2)]).join('').toUpperCase()
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
      {n?.summary && <><h2>{tr("要約")}</h2><p>{n.summary}</p></>}
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

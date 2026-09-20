import { botName } from '../lib/journey'
import { fmtTime, type Event, type RunDetail } from '../lib/api'
import { statusLabel, isSettled } from '../lib/journey'
import { getLang } from '../lib/i18n'

export function WorkProgress({run, events}: {run: RunDetail; events: Event[]}) {
  const en = getLang() === 'en'
  const roles = run.config_snapshot?.agents || {}
  const active = run.tasks.filter(t => t.status === 'running')
  const reviewing = active.some(t => roles[t.spec.owner]?.role === 'reviewer')
  const building = active.some(t => roles[t.spec.owner]?.role !== 'reviewer')
  const seen = new Set(events.map(e => e.type))
  const latest = events.at(-1)
  const settled = isSettled(run.status)
  const waiting = run.status === 'approval_required' || run.approvals.some(a => a.status === 'pending')
  const lastTask = [...events].reverse().find(e=>e.type==='task.started')
  const lastRole = roles[run.tasks.find(t=>t.spec.id===lastTask?.task_id)?.spec.owner || '']?.role
  const stage = run.status === 'completed' ? 4 : run.status === 'created' || run.status === 'queued' || (run.status === 'blocked' && !run.plan) ? 0 : !run.plan ? 1 : (reviewing && !building) || (settled && lastRole === 'reviewer') ? 3 : run.tasks.length && run.tasks.every(t=>['accepted','cancelled'].includes(t.status)) ? 4 : 2
  const labels = en ? ['Received','Plan','Research / create','Review','Finish'] : ['受付','計画','調査・作成','確認','終了']
  const reached = [true, !!run.plan || seen.has('run.started'), run.tasks.some(t=>t.attempt>0), seen.has('review.submitted') || run.tasks.some(t=>roles[t.spec.owner]?.role==='reviewer' && t.attempt>0), settled]
  const transitionNames: Record<string,string> = en ? {'run.started':'Execution started','run.resumed':'Work resumed','plan.accepted':'Plan ready','task.started':'Task started','task.review_pending':'Ready for review','review.submitted':'Review recorded','task.updated':'Task updated','run.completed':'Execution completed','run.interrupted':'Work interrupted','run.failed':'Execution failed','run.partial':'Partial result','run.cancelled':'Cancelled','approval.requested':'Approval requested'} : {'run.started':'実行開始','run.resumed':'作業を再開','plan.accepted':'進め方を決定','task.started':'担当の作業を開始','task.review_pending':'確認待ちへ','review.submitted':'確認結果を記録','task.updated':'作業内容・状態を更新','run.completed':'実行が完了','run.interrupted':'作業を中断','run.failed':'実行に失敗','run.partial':'途中成果を残して終了','run.cancelled':'取消','approval.requested':'承認待ちへ'}
  return <section className="work-progress pane" aria-label={en?'Work stages':'作業の状態遷移'}>
    <div className="progress-caption"><strong>{en?'Where the work is now':'いま、どこまで進んだか'}</strong><span>{run.tasks.filter(t=>t.status==='accepted').length} / {run.tasks.length} {en?'tasks finished':'作業を終了'}</span></div>
    <ol className="phase-track">{labels.map((label,i)=><li key={label} aria-current={i===stage?'step':undefined} className={`${i===stage?'is-current':''} ${reached[i]?'is-reached':''}`}><span className="phase-number">{i+1}</span><strong>{label}</strong><small>{i===stage ? waiting ? (en?'Approval needed':'承認待ち') : settled ? statusLabel(run.status,getLang()) : (en?'In progress':'進行中') : reached[i] ? (en?'Recorded':'記録あり') : (en?'Not reached':'未到達')}</small></li>)}</ol>
    <div className="progress-now" role="status"><b>{waiting ? (en?'Waiting for your approval':'あなたの承認を待っています') : statusLabel(run.status,getLang())}</b><span>{active.length && !settled ? active.map(t=>`${roles[t.spec.owner]?.display_name || botName(roles[t.spec.owner]?.role || t.spec.owner,getLang())}：${t.spec.objective}`).join(' / ') : !run.plan && !settled ? (en?'The coordinator is preparing assignments. Other bots are waiting.':'まとめ役が担当と進め方を決めています。他のボットは割り当て待ちです。') : (en?'Recorded stages do not guarantee artifact correctness.':'段階の到達は、成果物の正しさを保証するものではありません。')}</span></div>
    <div className="progress-foot"><span>{en?'Last work record':'最後の作業記録'}：{latest?fmtTime(latest.recorded_at):'—'}</span><span>{en?'Creation ↔ review can repeat when corrections are needed.':'修正が必要な場合は「作成 ⇄ 確認」を繰り返します。'}</span></div>
    <details className="stage-history"><summary>{en?'See state changes':'状態が変わった履歴を見る'}</summary><p>{en?'Latest 30 recorded changes. Full history is in the detailed work record.':'直近30件を表示します。全履歴は詳しい作業記録で確認できます。'}</p><ol>{events.filter(e=>transitionNames[e.type]).slice(-30).map(e=><li key={e.event_id}><time>{fmtTime(e.recorded_at)}</time><span>{transitionNames[e.type]}{e.task_id && ` · ${roles[run.tasks.find(t=>t.spec.id===e.task_id)?.spec.owner || '']?.display_name || botName(roles[run.tasks.find(t=>t.spec.id===e.task_id)?.spec.owner || '']?.role || e.actor_id,getLang())}`}{e.payload.action==='revise' ? (en?' · Correction requested':' · 修正へ戻る'):''}</span></li>)}</ol></details>
  </section>
}

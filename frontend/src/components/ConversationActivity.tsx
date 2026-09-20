import { botName } from '../lib/journey'
import { fmtTime, type Event, type RunDetail } from '../lib/api'
import { getLang } from '../lib/i18n'

/** Execution feedback, deliberately outside the delivered-message log. */
export default function ConversationActivity({ run, events, connection }: { run: RunDetail; events: Event[]; connection: string }) {
  const en = getLang() === 'en'
  const active = ['created', 'queued', 'planning', 'running'].includes(run.status)
  const approval = run.status === 'approval_required' || run.approvals.some(item => item.status === 'pending')
  if (!active && !approval) return null
  const connected = connection === 'live' && run.live
  const moving = active && connected && !approval
  const tasks = run.tasks.filter(task => task.status === 'running')
  const agents = run.config_snapshot?.agents || {}
  const label = !connected ? (en ? 'Checking the connection…' : '接続を確認中')
    : approval ? (en ? 'Waiting for your approval' : '承認待ち')
    : run.status === 'queued' || run.status === 'created' ? (en ? 'Waiting to start…' : '開始待ち')
    : run.status === 'planning' ? (en ? 'Planning the work…' : '考え中')
    : (en ? 'Working on your request…' : '作業中')
  const taskText = tasks.map(task => `${agents[task.spec.owner]?.display_name || botName(agents[task.spec.owner]?.role || task.spec.owner, getLang())}：${task.spec.objective}`).join(' / ')
  const latest = events.at(-1)
  return <div className={`conversation-processing${moving ? ' is-processing' : ''}`} data-processing={moving ? 'active' : 'waiting'}>
    <div className="processing-heading" role="status"><span className="processing-dots" aria-hidden="true"><i /><i /><i /></span><strong>{label}</strong></div>
    <details className="processing-more"><summary>{en ? 'Details' : '詳細'}</summary>
    {connected && !approval && <p className="processing-detail">{run.status === 'planning' ? (en ? 'The coordinator is preparing assignments for the team.' : (run.inputs.team_selection === 'adaptive' && !run.config_snapshot?.team_recommendation ? '依頼に合う専門性と人数を考えています。' : 'チームで担当と作業の順番を決めています。')) : taskText || (en ? 'Waiting for the next recorded response from the team.' : 'チームから次の作業記録や応答が届くのを待っています。')}</p>}
    <p className="processing-note">{!connected ? (en ? 'The last known state is shown. It will refresh when the connection returns.' : '最後に取得した状態を表示しています。接続が戻ると更新します。') : approval ? (en ? 'Review the proposed action above to continue.' : '続けるには、上の承認内容を確認してください。') : (en ? 'Messages and results appear as they arrive.' : '発言や成果物が届くと、ここに表示します。')}{latest && <span>{en ? 'Last work record: ' : '最後の作業記録：'}{fmtTime(latest.recorded_at)}</span>}</p>
    </details>
  </div>
}

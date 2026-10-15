import { useEffect, useState } from 'react'
import { getLang } from '../lib/i18n'

type Ready = { ready: boolean; workflow: 'team' | 'document'; disk_free_bytes: number; sandbox_backend: string; execution_dispatcher_ready: boolean; configuration_problems: string[] }
type Audit = { id: number; recorded_at: number; subject: string | null; method: string; route: string; outcome: string; status: number }

// Plain names for the isolation backend reported by /api/admin/ready (runtime/sandbox.py).
const SANDBOX: Record<string, [string, string]> = {
  docker: ['Docker コンテナで隔離', 'Isolated in a Docker container'],
  'sandbox-exec': ['macOS の seatbelt を検出', 'macOS seatbelt detected'],
  subprocess: ['隔離なし（そのまま実行）', 'No isolation (runs directly)'],
  none: ['利用できる隔離環境がありません', 'No isolation backend available'],
  not_required: ['不要（この構成ではコマンド実行なし）', 'Not required (no command execution in this configuration)'],
}

export default function Operations({ secured }: { secured: boolean }) {
  const [ready, setReady] = useState<Ready | null>(null)
  const [records, setRecords] = useState<Audit[]>([])
  const [error, setError] = useState('')
  const [updated, setUpdated] = useState<Date | null>(null)
  const [refresh, setRefresh] = useState(0)
  const ja = getLang() !== 'en'
  useEffect(() => {
    let alive = true
    const controller = new AbortController()
    const tick = async () => {
      try {
        const responses = await Promise.all(['/api/admin/ready', '/api/admin/audit?latest=true&limit=30'].map(url => fetch(url, { signal: controller.signal })))
        if (responses.some(r => r.status === 401)) { window.dispatchEvent(new Event('agentteam:unauthorized')); return }
        if (![200, 503].includes(responses[0].status) || !responses[1].ok) throw new Error('unavailable')
        const [state, audit] = await Promise.all(responses.map(r => r.json()))
        if (!alive) return
        setReady(state); setRecords(audit.reverse()); setUpdated(new Date()); setError('')
      } catch {
        if (alive) { setReady(null); setRecords([]); setError(ja ? '状態を取得できません。接続と権限を確認してください。' : 'Cannot retrieve status. Check connection and access.') }
      }
    }
    void tick()
    const timer = setInterval(tick, 30000)
    return () => { alive = false; controller.abort(); clearInterval(timer) }
  }, [refresh, ja])
  return <section className="stack operations">
    <div className="row"><h1>{ja ? '運用状況' : 'Operations'}</h1><button className="btn" onClick={() => setRefresh(n => n + 1)}>{ja ? '更新' : 'Refresh'}</button></div>
    <p className="muted">{ja ? '実行基盤の状態と直近のアクセス記録です。モデルの応答品質・外部サービスの現在の稼働を保証するものではありません。' : 'Execution prerequisites and recent access records. These checks do not establish model output quality or current provider availability.'}</p>
    {error && <p role="alert" className="err">{error}</p>}
    {ready ? <div className="card stack" aria-label={ja ? '稼働条件' : 'Readiness'}>
      <strong>{ready.ready ? (ja ? '実行に必要な条件を確認済み' : 'Execution prerequisites available') : (ja ? '実行条件の確認が必要' : 'Execution prerequisites need attention')}</strong>
      <p className="muted">{ja ? `確認対象: 現在のチーム設定・${ready.workflow === 'document' ? '文書作業' : '通常の作業方式'}。依頼ごとの実行可否は、選択されたメンバーと作業方式で別に判定します。` : `Scope: current team configuration, ${ready.workflow === 'document' ? 'document' : 'standard'} workflow. Each request is checked separately using its selected members and workflow.`}</p>
      <dl className="kv"><dt>{ja ? '実行キュー' : 'Queue dispatcher'}</dt><dd>{ready.execution_dispatcher_ready ? 'OK' : (ja ? '停止' : 'Stopped')}</dd>
        <dt>{ja ? 'ディスク空き容量' : 'Free disk'}</dt><dd>{(ready.disk_free_bytes / 1024 ** 3).toFixed(1)} GiB</dd>
        <dt>{ja ? '実行環境' : 'Sandbox'}</dt><dd>{SANDBOX[ready.sandbox_backend]?.[ja ? 0 : 1] ?? ready.sandbox_backend}</dd></dl>
      {!ready.ready && (() => {
        // The server permits seatbelt locally, but secured command tools require Docker.
        const reasons: string[] = []
        if (!ready.execution_dispatcher_ready) reasons.push(ja ? '実行キューが止まっています。' : 'The queue dispatcher is stopped.')
        if (ready.disk_free_bytes < 500 * 1024 ** 2) reasons.push(ja ? 'ディスクの空きが 500 MiB 未満です。' : 'Less than 500 MiB of disk is free.')
        if (secured && ['none', 'subprocess', 'sandbox-exec'].includes(ready.sandbox_backend)) reasons.push(ja ? 'このチーム設定にはコマンドを実行できるメンバーがいます。認証付きサービスのコマンド実行には Docker が必要です。Docker を利用する設定とサーバーからの接続を確認してください。' : 'This team configuration includes members that can execute commands. Command execution in an authenticated service requires Docker. Check that Docker is configured for use and reachable from the server.')
        else if (['none', 'subprocess'].includes(ready.sandbox_backend)) reasons.push(ja ? 'コマンドを隔離して実行する環境がありません。Docker を利用する設定と接続、またはローカル実行用の macOS seatbelt を確認してください。' : 'No isolation is available for command execution. Check Docker configuration and connectivity, or macOS seatbelt for local execution.')
        for (const p of ready.configuration_problems) reasons.push(p === 'capability_check' ? (ja ? 'モデルの接続確認が未完了です。管理者による確認が必要です。' : 'The model connection has not been verified. An administrator needs to check it.') : p)
        if (!reasons.length) reasons.push(ja ? '原因を特定できませんでした。サーバーの記録を確認してください。' : 'The cause could not be identified. Check the server log.')
        return <ul className="err">{reasons.map(r => <li key={r}>{r}</li>)}</ul>
      })()}
      <small className="muted">{ja ? '取得時刻' : 'Checked'}: {updated?.toLocaleTimeString()}</small>
    </div> : !error && <p role="status">{ja ? '状態を取得中…' : 'Loading status…'}</p>}
    <h2>{ja ? '直近の監査記録' : 'Recent audit records'}</h2>
    <div style={{ overflowX: 'auto' }}><table className="audit-table">
      <thead><tr>{(ja ? ['時刻', '利用者', '操作', '結果'] : ['Time', 'Subject', 'Operation', 'Outcome']).map(label => <th key={label} style={{ textAlign: 'left' }}>{label}</th>)}</tr></thead>
      <tbody>{records.length === 0 && !error && ready && <tr><td colSpan={4} className="muted">{ja ? '記録はまだありません。' : 'No records yet.'}</td></tr>}{records.map(row => <tr key={row.id}><td>{new Date(row.recorded_at * 1000).toLocaleString()}</td><td>{row.subject || '—'}</td><td><code>{row.method} {row.route}</code></td><td>{row.outcome} {row.status || ''}</td></tr>)}</tbody>
    </table></div>
  </section>
}

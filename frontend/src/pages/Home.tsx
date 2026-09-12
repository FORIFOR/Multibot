import { t } from '../lib/i18n'
import { useEffect, useState } from 'react'
import { api, ApiError, fmtDate, money, type Config, type Run } from '../lib/api'
import { Link } from '../lib/router'

export default function Home({ nav }: { nav: (p: string) => void }) {
  const [goal, setGoal] = useState('')
  const [text, setText] = useState('')
  const [urls, setUrls] = useState('')
  const [budget, setBudget] = useState('')
  const [cfg, setCfg] = useState<Config | null>(null)
  const [runs, setRuns] = useState<Run[]>([])
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [problems, setProblems] = useState<{ code: string; message: string }[]>([])

  useEffect(() => { api.config().then(setCfg).catch(() => null); api.runs().then(setRuns).catch(() => null) }, [])

  const start = async () => {
    setBusy(true); setErr(null); setProblems([])
    try {
      const run = await api.createRun({
        goal, inputs: { text, urls: urls.split(/\s+/).filter(Boolean), files: [] },
        budget_usd: budget ? Number(budget) : null,
      })
      nav(`/runs/${run.run_id}`)
    } catch (e) {
      if (e instanceof ApiError && e.status === 409 && e.body?.problems) setProblems(e.body.problems)
      else setErr(String(e))
    } finally { setBusy(false) }
  }
  const ready = cfg ? cfg.problems.length === 0 : false
  const model = cfg ? cfg.defaults.model : '…'
  return (
    <div>
      <section className="hero">
        <div className="reveal">
          <h1>{t("依頼は一度。")}<br />{t("チームが作り、")}<em>{t("確かめ")}</em>{t("、経緯を残す。")}</h1>
          <p className="lede">{t("Master が成果物と完了条件を決め、必要な Bot だけが実際に作業します。成果物・Bot 間の実メッセージ・時系列は同じ実行記録から表示されます。台本の会話や固定の成功ログは使いません。")}</p>
          {cfg && (
            <div className={'banner ' + (ready ? 'ok' : 'warn')} style={{ marginTop: 18 }}>
              {ready ? <>{t("接続")} <code>{cfg.defaults.connection_id}</code> {t("/ モデル")} <code>{model}</code> は疎通確認済み。予算上限 {money(cfg.limits.budget_usd)} / run。</>
                : <>開始前に設定が必要です：{cfg.problems.map((p) => p.message).join(' / ')} → <Link to="/settings" nav={nav}>{t("設定を開く")}</Link></>}
            </div>
          )}
        </div>
        <div className="ask reveal">
          <textarea className="input" placeholder={t("例: この製品の説明をもとに、紹介LPとREADME、SNS投稿案を作って。足りない情報は調べて、公開前の状態まで仕上げて。")} value={goal} onChange={(e) => setGoal(e.target.value)} />
          <details className="more">
            <summary>{t("添付・URL・予算")}</summary>
            <div className="stack" style={{ marginTop: 8 }}>
              <textarea className="input" placeholder={t("製品説明などのテキスト（任意）")} value={text} onChange={(e) => setText(e.target.value)} />
              <input className="input" placeholder={t("参照URL（空白区切り、任意）")} value={urls} onChange={(e) => setUrls(e.target.value)} />
              <input className="input" placeholder={`この run の予算上限 USD（既定 ${cfg ? cfg.limits.budget_usd : '…'}）`} value={budget} onChange={(e) => setBudget(e.target.value)} />
            </div>
          </details>
          <div className="foot">
            <span className="muted small">{t("外部への投稿・送信は行いません（草案まで）。")}</span>
            <span className="spacer" />
            <button className="btn signal" disabled={!goal.trim() || busy || !ready} onClick={start}>{busy ? '開始中…' : t('開始')}</button>
          </div>
          {err && <p className="err">{err}</p>}
          {problems.length > 0 && <div className="banner">{problems.map((p) => <div key={p.code}>{p.message}</div>)} <Link to="/settings" nav={nav}>{t("設定へ")}</Link></div>}
        </div>
      </section>
      <section className="runs-list">
        <h3>{t("最近の実行")}</h3>
        {runs.length === 0 && <p className="muted">{t("まだ実行はありません。")}</p>}
        {runs.map((r) => (
          <Link key={r.run_id} to={`/runs/${r.run_id}`} nav={nav} className="run-row">
            <span className={'tag status-' + r.status}>{r.status}</span>
            <span className="goal">{r.goal}{r.provider_kind === 'fake' && <> <span className="tag fake">FAKE</span></>}</span>
            <span className="mono muted">{money(r.usage.cost_usd)} · {r.usage.model_calls} calls</span>
            <span className="muted small">{fmtDate(r.created_at)}</span>
          </Link>
        ))}
      </section>
    </div>
  )
}

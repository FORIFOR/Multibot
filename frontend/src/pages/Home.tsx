import { t } from '../lib/i18n'
import Orb from '../components/Orb'
import { useEffect, useState, type ChangeEvent } from 'react'
import { api, ApiError, fmtDate, money, type Config, type Run } from '../lib/api'
import { Link } from '../lib/router'

const MAX_ATTACHMENT_BYTES = 512 * 1024
const ATTACHMENT_EXTENSIONS = new Set(['.txt', '.md', '.markdown', '.csv'])

function extensionOf(name: string) {
  const dot = name.lastIndexOf('.')
  return dot >= 0 ? name.slice(dot).toLowerCase() : ''
}

export default function Home({ nav, readOnly = false, canConfigure = true }: { nav: (p: string) => void; readOnly?: boolean; canConfigure?: boolean }) {
  const [goal, setGoal] = useState('')
  const [text, setText] = useState('')
  const [urls, setUrls] = useState('')
  const [files, setFiles] = useState<{ name: string; content: string }[]>([])
  const [fileError, setFileError] = useState<string | null>(null)
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
        goal, inputs: { text, urls: urls.split(/\s+/).filter(Boolean), files },
        budget_usd: budget ? Number(budget) : null,
      })
      nav(`/runs/${run.run_id}`)
    } catch (e) {
      if (e instanceof ApiError && e.status === 409 && e.body?.problems) setProblems(e.body.problems)
      else setErr(String(e))
    } finally { setBusy(false) }
  }
  const onFiles = async (event: ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(event.currentTarget.files || [])
    // Let the same file be selected again after a correction/removal.
    event.currentTarget.value = ''
    if (selected.length === 0) return
    const accepted: { name: string; content: string }[] = []
    const errors: string[] = []
    for (const file of selected) {
      const ext = extensionOf(file.name)
      if (!ATTACHMENT_EXTENSIONS.has(ext)) {
        errors.push(`${file.name}: ${t('txt / md / csv のみ添付できます。')}`)
        continue
      }
      if (file.size > MAX_ATTACHMENT_BYTES) {
        errors.push(`${file.name}: ${t('512KB 以下のファイルを選んでください。')}`)
        continue
      }
      try {
        accepted.push({ name: file.name, content: await file.text() })
      } catch {
        errors.push(`${file.name}: ${t('ファイルを読み込めませんでした。')}`)
      }
    }
    if (accepted.length) {
      setFiles((prev) => [...prev.filter((old) => !accepted.some((next) => next.name === old.name)), ...accepted])
    }
    setFileError(errors.length ? errors.join(' ') : null)
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
                : <>開始前に設定が必要です：{cfg.problems.map((p) => p.message).join(' / ')} {canConfigure ? <>→ <Link to="/settings" nav={nav}>{t("設定を開く")}</Link></> : <span> 管理者に接続設定の確認を依頼してください。</span>}</>}
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
              <div className="attachment-picker">
                <label className="attachment-label" htmlFor="run-attachments">{t('依頼に含める資料')} <span className="muted">{t('txt / md / csv、1ファイル512KBまで')}</span></label>
                <input id="run-attachments" className="input" type="file" accept=".txt,.md,.markdown,.csv,text/plain,text/markdown,text/csv" multiple onChange={onFiles} />
                {files.length > 0 && <div className="attachment-list" aria-label={t('添付済み資料')}>
                  {files.map((file) => <div className="attachment-item" key={file.name}>
                    <span className="mono">{file.name}</span><span className="muted small">{file.content.length.toLocaleString()} {t('文字')}</span>
                    <button type="button" className="btn sm ghost" onClick={() => setFiles((prev) => prev.filter((item) => item.name !== file.name))}>{t('削除')}</button>
                  </div>)}
                </div>}
                {fileError && <p className="err small" role="alert">{fileError}</p>}
              </div>
              <input className="input" placeholder={`この run の予算上限 USD（既定 ${cfg ? cfg.limits.budget_usd : '…'}）`} value={budget} onChange={(e) => setBudget(e.target.value)} />
            </div>
          </details>
          <div className="foot">
            <span className="muted small">{readOnly ? '閲覧権限でログインしています。' : t("外部への投稿・送信は行いません（草案まで）。")}</span>
            <span className="spacer" />
            {busy && <Orb state="thinking" size={36} title={t("開始中…")} />}
            <button className="btn signal" disabled={readOnly || !goal.trim() || busy || !ready} onClick={start}>{busy ? t('開始中…') : t('開始')}</button>
          </div>
          {err && <p className="err">{err}</p>}
          {problems.length > 0 && <div className="banner">{problems.map((p) => <div key={p.code}>{p.message}</div>)} {canConfigure && <Link to="/settings" nav={nav}>{t("設定へ")}</Link>}</div>}
        </div>
      </section>
      <section className="runs-list">
        <h3>{t("最近の実行")}</h3>
        {runs.length === 0 && <p className="muted">{t("まだ実行はありません。")}</p>}
        {runs.map((r) => (
          <Link key={r.run_id} to={`/runs/${r.run_id}`} nav={nav} className="run-row">
            <span className={'tag status-' + r.status}>{r.status === 'queued' ? t('実行待ち') : r.status}</span>
            <span className="goal">{r.goal}{r.provider_kind === 'fake' && <> <span className="tag fake">FAKE</span></>}</span>
            <span className="mono muted">{money(r.usage.cost_usd)} · {r.usage.model_calls} calls</span>
            <span className="muted small">{fmtDate(r.created_at)}</span>
          </Link>
        ))}
      </section>
    </div>
  )
}

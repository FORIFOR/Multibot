import { t, getLang } from '../lib/i18n'
import Journey from '../components/Journey'
import BotAvatar from '../components/BotAvatar'
import { friendlyProblem, roleLabel, statusLabel } from '../lib/journey'
import { takeDraftGoal, welcomed } from '../lib/welcome'
import '../journey.css'
import '../welcome.css'
import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from 'react'
import { api, ApiError, fmtDate, money, type Config, type Run } from '../lib/api'
import { Link } from '../lib/router'

const MAX_ATTACHMENT_BYTES = 512 * 1024
const ATTACHMENT_EXTENSIONS = new Set(['.txt', '.md', '.markdown', '.csv'])

function extensionOf(name: string) {
  const dot = name.lastIndexOf('.')
  return dot >= 0 ? name.slice(dot).toLowerCase() : ''
}

export default function Home({ nav, readOnly = false, canConfigure = true }: { nav: (p: string) => void; readOnly?: boolean; canConfigure?: boolean }) {
  const busyRef = useRef(false)
  const goalRef = useRef<HTMLTextAreaElement>(null)
  const en = getLang() === 'en'
  const [goal, setGoal] = useState('')
  const [text, setText] = useState('')
  const [urls, setUrls] = useState('')
  const [files, setFiles] = useState<{ name: string; content: string }[]>([])
  const [fileError, setFileError] = useState<string | null>(null)
  const [budget, setBudget] = useState('')
  const [cfg, setCfg] = useState<Config | null>(null)
  const [runs, setRuns] = useState<Run[]>([])
  const [loaded, setLoaded] = useState(false)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [problems, setProblems] = useState<{ code: string; message: string }[]>([])

  useEffect(() => { api.config().then(setCfg).catch(() => setErr(en ? 'Could not load the team. Reload to try again.' : 'チームを読み込めませんでした。再読み込みしてください。')); api.runs().then(r => { setRuns(r); setLoaded(true) }).catch(() => null)
    // A request chosen on the welcome page arrives as a draft; it is never started automatically.
    const draft = takeDraftGoal(); if (draft) setGoal(draft) }, [])

  const start = async (event: FormEvent) => {
    event.preventDefault()
    if (busyRef.current || readOnly || !goal.trim() || !cfg || cfg.problems.length) return
    const cap = budget ? Number(budget) : null
    if (cap !== null && (!Number.isFinite(cap) || cap <= 0)) { setErr(en ? 'Choose a positive budget.' : '予算は0より大きい金額を入力してください。'); return }
    busyRef.current = true
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
    } finally { busyRef.current = false; setBusy(false) }
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
  const teammates = cfg ? cfg.agents.filter(a => a.enabled).slice(0, 5) : []
  const companion = teammates.find(a => a.role === 'master') || teammates[0]
  // Offer the introduction until it has been seen or the first request exists. Never block the input with it.
  const firstVisit = loaded && runs.length === 0 && !welcomed()
  return (
    <div className="simple-home">
      <Journey current="request" />
      <section className="hero">
        <div className="home-welcome">
          {/* The coordinator is the one you talk to; the rest of the team stands behind it. */}
          <div className="home-companion">
            {companion && <BotAvatar id={companion.id} role={companion.role} emoji={companion.emoji} name={companion.display_name || roleLabel(companion.role, getLang())} state="idle" size="stage" />}
            <div className="companion-says">
              <p>{en ? `I'm your ${roleLabel(companion?.role || 'master', 'en').toLowerCase()}. I split your request across the team, and hand back what we checked.` : `${roleLabel(companion?.role || 'master', 'ja')}です。お願いをチームに分けて、確かめたものをお渡しします。`}</p>
              {firstVisit && <Link to="/welcome" nav={nav} className="companion-link">{en ? 'New here? Meet the team →' : 'はじめての方へ：チームを紹介します →'}</Link>}
            </div>
          </div>
          <div className="home-team" aria-label={en ? 'Your team' : 'あなたのチーム'}>{teammates.filter(a => a.id !== companion?.id).map(a => <BotAvatar key={a.id} id={a.id} role={a.role} emoji={a.emoji} name={a.display_name || roleLabel(a.role, getLang())} state="idle" />)}</div>
          <h1>{en ? 'What shall we make' : '今日は、何を'}<br />{en ? 'together?' : '一緒につくろう？'}</h1>
          <p className="lede">{en ? 'Tell your team what you need. They will create, check and revise the work.' : 'やりたいことを教えてください。チームが分担して、つくって、確かめます。'}</p>
          <div className="request-examples" aria-label={en ? 'Request ideas' : 'お願いの例'}>{(en ? ['Summarize my notes', 'Make a comparison table', 'Review my writing'] : ['資料を分かりやすくまとめて', '比較表をつくって', '文章をチェックして']).map((example, i) => <button type="button" key={example} disabled={busy || readOnly} onClick={() => { setGoal(example); goalRef.current?.focus() }}><span aria-hidden="true">{['📝','🔎','✏️'][i]}</span>{example}</button>)}</div>
        </div>
        <form className="ask" onSubmit={start}>
          <label className="ask-label" htmlFor="request-goal">{en ? 'What would you like your team to do?' : 'チームにお願いしたいこと'}</label>
          <textarea id="request-goal" ref={goalRef} className="input" required placeholder={en ? 'For example: turn these notes into a clear comparison report.' : '例：この資料をもとに、分かりやすい比較レポートをつくって。'} value={goal} onChange={e => setGoal(e.target.value)} disabled={busy || readOnly} />
          <details className="more">
            <summary>{en ? "Add materials or set a budget" : "資料を添える・予算を決める"}</summary>
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
              <input className="input" type="number" min="0.01" step="0.01" aria-label={en ? "Budget limit in USD" : "予算上限（米ドル）"} placeholder={en ? "Budget limit in USD" : "予算上限（米ドル）"} value={budget} onChange={(e) => setBudget(e.target.value)} />
            </div>
          </details>
          <div className="foot">
            <span className="muted small">{readOnly ? '閲覧権限でログインしています。' : t("外部への投稿・送信は行いません（草案まで）。")}</span>
            <span className="spacer" />
            <button className="btn signal" type="submit" disabled={readOnly || !goal.trim() || busy || !ready}>{busy ? (en ? "Starting…" : "お願いしています…") : (en ? "Ask the team" : "チームにお願いする")}</button>
          </div>
          {cfg && <p className="request-budget">{en ? 'Budget limit' : '予算上限'}: {money(budget && Number.isFinite(Number(budget)) && Number(budget)>0 ? Number(budget) : cfg.limits.budget_usd)} {en ? 'per request. Work pauses at its configured limits.' : '／1回。設定した上限に達すると停止します。'}</p>}
          {!ready && <div className="setup-help">{cfg ? (en ? 'One-time setup is needed before your first request.' : '最初のお仕事の前に、接続の準備が必要です。') : (en ? 'Checking the team…' : 'チームを確認しています…')}{canConfigure && cfg && <Link to="/settings" nav={nav}>{en ? 'Prepare my team' : 'チームを準備する'} →</Link>}{cfg?.problems.length ? <details><summary>{en ? 'Setup details' : '設定の詳細'}</summary>{cfg.problems.map((p,i)=><p key={i}>{p.message}</p>)}</details>:null}</div>}
          {err && <p className="err" role="alert">{err}</p>}
          {problems.length > 0 && <div className="banner">{problems.map((p) => <div key={p.code} title={p.message}>{friendlyProblem(p, getLang())}</div>)} {canConfigure && <Link to="/settings" nav={nav}>{t("設定へ")}</Link>}</div>}
        </form>
      </section>
      <section className="runs-list">
        <h2>{en ? "Your recent requests" : "これまでのお願い"}</h2>
        {runs.length === 0 && <p className="muted">{t("まだ実行はありません。")}</p>}
        {runs.map((r) => (
          <Link key={r.run_id} to={`/runs/${r.run_id}`} nav={nav} className="run-row">
            <span className={'tag status-' + r.status}>{statusLabel(r.status,getLang())}</span>
            <span className="goal">{r.goal}{r.provider_kind === 'fake' && <> <span className="tag fake">{en ? 'Test' : 'テスト'}</span></>}</span>
            <span className="mono muted">{money(r.usage.cost_usd)}</span>
            <span className="muted small">{fmtDate(r.created_at)}</span>
          </Link>
        ))}
      </section>
    </div>
  )
}

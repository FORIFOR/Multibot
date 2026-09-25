import { botName } from '../lib/journey'
import { t, getLang } from '../lib/i18n'
import Journey from '../components/Journey'
import BotAvatar from '../components/BotAvatar'
import { botIcon } from '../lib/bot-presentation'
import { friendlyProblem, roleLabel, statusLabel } from '../lib/journey'
import { takeDraftGoal, welcomed } from '../lib/welcome'
import '../journey.css'
import '../welcome.css'
import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from 'react'
import { api, ApiError, fmtDate, money, type Config, type Run } from '../lib/api'
import { readRequestDraft, saveRequestDraft, clearRequestDraft } from '../lib/request-draft'
import { Link } from '../lib/router'
import { textDeliverySchema } from '../lib/text-delivery'

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
  const [draft] = useState(readRequestDraft)
  const [adaptiveTeam,setAdaptiveTeam] = useState(draft.adaptiveTeam !== false)
  const [selectedAgentIds, setSelectedAgentIds] = useState<string[] | undefined>(draft.selectedAgentIds)
  const [draftSaved, setDraftSaved] = useState(true)
  const [goal, setGoal] = useState(draft.goal)
  const [text, setText] = useState(draft.text)
  const [urls, setUrls] = useState(draft.urls)
  const [files, setFiles] = useState<{ name: string; content: string }[]>(draft.files)
  const [fileError, setFileError] = useState<string | null>(null)
  const [budget, setBudget] = useState(draft.budget)
  const [outputPath,setOutputPath] = useState(draft.outputPath || '')
  const [documentWorkflow,setDocumentWorkflow] = useState(draft.documentWorkflow === true)
  const [minChars,setMinChars] = useState(draft.minChars || '')
  const [maxChars,setMaxChars] = useState(draft.maxChars || '')
  const [excludedPhrases,setExcludedPhrases] = useState(draft.excludedPhrases || '')
  const [cfg, setCfg] = useState<Config | null>(null)
  const [runs, setRuns] = useState<Run[]>([])
  const [loaded, setLoaded] = useState(false)
  // Failed loads must not read as "no runs yet" or "still checking".
  const [runsFailed, setRunsFailed] = useState(false)
  const [cfgFailed, setCfgFailed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [problems, setProblems] = useState<{ code: string; message: string }[]>([])
  // A request that got no answer may or may not have been created. Until the list has been checked, do not offer
  // to send it again from here.
  const [ambiguous, setAmbiguous] = useState(false)

  useEffect(() => { api.config().then(setCfg).catch(() => { setCfgFailed(true); setErr(en ? 'Could not load the team. Reload to try again.' : 'チームを読み込めませんでした。再読み込みしてください。') }); api.runs().then(r => { setRuns(r); setLoaded(true) }).catch(() => setRunsFailed(true))
    // A request chosen on the welcome page arrives as a draft; it is never started automatically.
    const draft = takeDraftGoal(); if (draft) setGoal(draft) }, [])

  useEffect(() => { setDraftSaved(saveRequestDraft({ goal, text, urls, files, budget, outputPath, minChars, maxChars, excludedPhrases, documentWorkflow, adaptiveTeam, selectedAgentIds })) }, [goal, text, urls, files, budget, outputPath, minChars, maxChars, excludedPhrases, documentWorkflow, adaptiveTeam, selectedAgentIds])

  const start = async (event: FormEvent) => {
    event.preventDefault()
    if (busyRef.current || readOnly || !goal.trim() || !cfg || (adaptiveTeam && cfg.problems.length)) return
    if (!adaptiveTeam && selectedAgentIds?.length === 0) { setErr(en ? 'Choose at least one teammate.' : '参加する仲間を選んでください。'); return }
    const cap = budget ? Number(budget) : null
    if (cap !== null && (!Number.isFinite(cap) || cap <= 0)) { setErr(en ? 'Choose a positive budget.' : '予算は0より大きい金額を入力してください。'); return }
    const min = minChars === '' ? undefined : Number(minChars), max = maxChars === '' ? undefined : Number(maxChars)
    if ((min !== undefined && (!Number.isInteger(min) || min < 0)) || (max !== undefined && (!Number.isInteger(max) || max < 1)) || (min !== undefined && max !== undefined && min > max) || ((min !== undefined || max !== undefined || excludedPhrases.trim()) && !outputPath.trim())) {
      setErr(en ? 'Choose an output filename and a valid character range.' : '保存するファイル名と正しい文字数の範囲を入力してください。'); return
    }
    const delivery = outputPath.trim() ? [{logical_path:outputPath.trim(),input_format:'text',json_schema:textDeliverySchema(min, max, excludedPhrases)}] : []
    if (documentWorkflow && (!delivery.length || urls.trim() || !(text.trim() || files.some(f => f.content.trim())))) {
      setErr(en ? 'For the document workflow, attach or paste source text, specify an output filename, and remove URL inputs.' : '文書作成では、資料を添付または貼り付け、ファイル名を指定してください。URL入力には通常の進め方を使ってください。'); return
    }
    busyRef.current = true
    setBusy(true); setErr(null); setProblems([]); setAmbiguous(false)
    try {
      const run = await api.createRun({
        goal, inputs: { team_selection: adaptiveTeam && !documentWorkflow && cfg.defaults.team_mode !== 'single' ? 'adaptive' : 'fixed', ...(!adaptiveTeam && cfg.defaults.team_mode !== 'single' ? {selected_agent_ids: selectedAgentIds ?? cfg.agents.filter(a => a.enabled && !['master', 'reporter'].includes(a.role)).map(a => a.id)} : {}), text, urls: urls.split(/\s+/).filter(Boolean), files, delivery_requirements: delivery, ...(documentWorkflow ? {workflow: 'document' as const}: {}) },
        budget_usd: budget ? Number(budget) : null,
      })
      clearRequestDraft()
      nav(`/runs/${run.run_id}`)
    } catch (e) {
      if (e instanceof ApiError && e.status === 409 && e.body?.problems) setProblems(e.body.problems)
      else if (e instanceof ApiError && e.status === 503 && e.message === 'insufficient storage space') setErr(en ? 'Work has not started because the server has less than 500 MB of free storage. Your request and attachments are kept. Free storage, then try again.' : '保存先の空き容量が500MB未満のため、作業を開始できません。依頼と添付資料は残しています。空き容量を確保してから、もう一度お試しください。')
      else { if (!(e instanceof ApiError)) setAmbiguous(true); setErr(e instanceof ApiError ? String(e) : (en ? 'The response did not arrive. Your request may have been received. Check recent requests before explicitly retrying the unchanged request. Do not create a new request while the outcome is unknown.' : '応答を受け取れませんでした。依頼が届いている可能性があります。これまでのお願いを確認し、必要なら同じ内容で再試行してください。結果が分かるまで新しい依頼を作らないでください。')) }
      api.runs().then(setRuns).catch(() => {})
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
  const ready = cfg ? !adaptiveTeam || cfg.problems.length === 0 : false
  const teammates = cfg ? cfg.agents.filter(a => a.enabled && (!adaptiveTeam || a.role === 'master')) : []
  const companion = teammates.find(a => a.role === 'master') || teammates[0]
  // Offer the introduction until it has been seen or the first request exists. Never block the input with it.
  const firstVisit = loaded && runs.length === 0 && !welcomed()
  return (
    <div className="simple-home">
      <Journey current="request" />
      <section className="hero">
        <div className="home-intro">
          <h1>{en ? <>What shall we make{' '}<wbr />together?</> : <>今日は、何を<br />一緒につくろう？</>}</h1>
          <p className="lede">{en ? 'Tell your team what you need. Attach your material to receive a file with its check record.' : 'やりたいことを教えてください。資料を添えて依頼すると、確認の記録が付いたファイルを受け取れます。'}</p>
        </div>
        <form className="ask" onSubmit={start}>
          {/* The coordinator is the one you talk to; the rest of the team stands behind it. */}
          <div className="home-companion">
            {companion && <BotAvatar id={companion.id} role={companion.role} emoji={companion.emoji} name={companion.display_name || botName(companion.role, getLang())} state="idle" size="stage" />}
            <div className="home-team" role="group" aria-label={en ? 'Your team' : 'あなたのチーム'}>{teammates.filter(a => a.id !== companion?.id).map(a => <BotAvatar key={a.id} id={a.id} role={a.role} emoji={a.emoji} name={a.display_name || botName(a.role, getLang())} state="idle" />)}</div>
            <div className="companion-says">
              <strong className="companion-name">{companion?.display_name || botName(companion?.role || 'master', getLang())}<span>{roleLabel(companion?.role || 'master', getLang())}</span></strong>
              <p>{goal.trim() && ready ? (en ? 'Got it. Send it when you are ready and I will gather the right teammates.' : '受け取る準備ができました。送ってもらえたら、合う仲間を集めます。') : (en ? 'Tell me what you need. I split it across the team and hand back what we checked.' : 'お願いを聞かせてください。合う仲間を集め、完成まで一緒に進めます。')}</p>
              {firstVisit && <Link to="/welcome" nav={nav} className="companion-link">{en ? 'New here? Meet the team →' : 'はじめての方へ：チームを紹介します →'}</Link>}
            </div>
          </div>
          <div className="ask-tray"><div className="ask-field">
            <label className="ask-label" htmlFor="request-goal">{en ? 'What would you like your team to do?' : 'チームにお願いしたいこと'}</label>
            <textarea id="request-goal" ref={goalRef} className="input" required placeholder={en ? 'For example: turn these notes into a clear comparison report.' : '例：この資料をもとに、分かりやすい比較レポートをつくって。'} value={goal} onChange={e => setGoal(e.target.value)} disabled={busy || readOnly} />
            <div className="ask-foot">
              <details className="more">
                <summary>{en ? "Add materials or set a budget" : "資料を添える・予算を決める"}</summary>
                <div className="stack" style={{ marginTop: 8 }}>
                  <textarea className="input" aria-label={en ? "Source text" : "資料の本文"} placeholder={t("製品説明などのテキスト（任意）")} value={text} onChange={(e) => setText(e.target.value)} />
                  <input className="input" aria-label={en ? "Source URLs" : "参照URL"} placeholder={t("参照URL（空白区切り、任意）")} value={urls} onChange={(e) => setUrls(e.target.value)} />
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
              <details className="more"><summary>{en ? 'Check the output file (optional)' : '成果物の条件を指定する（任意）'}</summary>
                <p>{en ? 'The team must pass these checks before completion. Counts include Markdown and spaces; factual accuracy needs a separate review.' : '完了前に実ファイルを検査します。Markdown記号・空白・改行も文字数に含めます。内容の正確性は別途確認が必要です。'}</p>
                <label>{en ? 'Output filename' : '成果物のファイル名'}<input className="input" value={outputPath} onChange={e=>setOutputPath(e.target.value)} placeholder="guide.md" /></label>
                <label>{en ? 'Minimum characters' : '最小文字数'}<input className="input" type="number" min="0" step="1" value={minChars} onChange={e=>setMinChars(e.target.value)} /></label>
                <label>{en ? 'Maximum characters' : '最大文字数'}<input className="input" type="number" min="1" step="1" value={maxChars} onChange={e=>setMaxChars(e.target.value)} /></label>
                <label htmlFor="excluded-phrases">{en ? 'Phrases to exclude' : '使わない表現'}</label>
                <textarea id="excluded-phrases" className="input" rows={2} maxLength={2000} value={excludedPhrases} onChange={e=>setExcludedPhrases(e.target.value)} aria-describedby="excluded-phrases-help" />
                <p id="excluded-phrases-help">{en ? 'Optional, one phrase per line. Rejects these exact phrases anywhere in the file, including quotations. Letter case matters; paraphrases need a separate review.' : '任意・1行に1つ。引用を含む全文から、この表現を含むファイルを除外します。英字の大小は区別します。言い換えや内容の判断は別途確認します。'}</p>
                <label><input type="checkbox" checked={documentWorkflow} onChange={e=>setDocumentWorkflow(e.target.checked)} />{en ? 'Create one document from supplied material' : '添えた資料から1つの文書を作る'}</label>
                <p>{en ? 'A writer creates the file, then a separate reviewer checks it. Skips automatic task planning. Requires pasted text or attachments and an output filename; URL research uses the usual team workflow.' : '作成担当がファイルを作り、別の確認担当が照合します。作業計画の自動生成を省く進め方です。資料とファイル名が必要です。URLの調査は通常の進め方を使います。'}</p>
              </details>
              {cfg?.defaults.team_mode !== 'single' && <fieldset className={'request-team-picker' + (adaptiveTeam ? '' : ' is-choosing')} disabled={busy || readOnly}>
                <legend>{en ? 'Who will join?' : '一緒に取り組む仲間'}</legend>
                <div className="team-selection-mode">
                  <label><input type="radio" name="team-mode" checked={adaptiveTeam} disabled={documentWorkflow} onChange={() => setAdaptiveTeam(true)} />{en ? 'Recommend for me' : 'おまかせ'}</label>
                  <label><input type="radio" name="team-mode" checked={!adaptiveTeam} onChange={() => setAdaptiveTeam(false)} />{en ? 'Choose myself' : '自分で選ぶ'}</label>
                </div>
                {!adaptiveTeam && <>
                  <div className="request-character-grid">{cfg?.agents.filter(a => a.enabled && !['master', 'reporter'].includes(a.role)).map(a => {
                    const ids = selectedAgentIds ?? cfg.agents.filter(a => a.enabled && !['master', 'reporter'].includes(a.role)).map(a => a.id)
                    const selected = ids.includes(a.id)
                    return <button key={a.id} type="button" className="request-character" aria-pressed={selected} onClick={() => setSelectedAgentIds(selected ? ids.filter(id => id !== a.id) : [...ids, a.id])}>
                      <span aria-hidden="true" className="character-emoji">{botIcon(a.id, a.role, a.emoji)}</span>
                      <strong>{a.display_name || botName(a.role, getLang())}</strong>
                      <small>{a.role === 'reviewer' ? (en ? 'Can review' : '確認できる') : (en ? 'Can create' : '作成できる')}</small>
                      <span className="character-selection">{selected ? (en ? '✓ Joining' : '✓ 参加') : (en ? 'Add' : '選ぶ')}</span>
                    </button>
                  })}</div>
                  <p className="muted small">{en ? 'Your coordinator joins too. Names and voices stay as chosen; work is assigned for this request.' : '案内する仲間も一緒に参加します。名前・話し方はそのまま、仕事を依頼に合わせて割り当てます。'}</p>
                  {canConfigure && <Link to="/settings" nav={nav}>{en ? 'Edit characters →' : 'キャラクターを着せ替える →'}</Link>}
                </>}
                {adaptiveTeam && <p className="muted small">{documentWorkflow ? (en ? 'Document workflow uses the configured team.' : '文書作成では設定済みのチームを使います。') : (en ? 'A new team is recommended for this task.' : '依頼に合う人数とキャラクターをおすすめします。')}</p>}
              </fieldset>}
              <div className="foot"><button className="btn signal" type="submit" disabled={readOnly || !goal.trim() || busy || !ready || ambiguous}>{busy ? (en ? "Starting…" : "お願いしています…") : (en ? "Ask the team" : "チームにお願いする")}</button></div>
            </div>
          </div></div>
          <p className="ask-hint">{readOnly ? '閲覧権限でログインしています。' : (en ? 'Review the result before selecting a version.' : 'できたものを確認してから、使う版を選べます。')}</p>
          {!ready && <div className="setup-help">{cfg ? (en ? 'One-time setup is needed before your first request.' : '最初のお仕事の前に、接続の準備が必要です。') : cfgFailed ? (en ? 'The team could not be loaded, so requests cannot be sent yet. Reload to try again.' : 'チームを読み込めなかったため、まだお願いを送れません。再読み込みしてください。') : (en ? 'Checking the team…' : 'チームを確認しています…')}{canConfigure && cfg && <Link to="/settings" nav={nav}>{en ? 'Prepare my team' : 'チームを準備する'} →</Link>}{cfg?.problems.length ? <details><summary>{en ? 'Setup details' : '設定の詳細'}</summary>{cfg.problems.map((p,i)=><p key={i}>{p.message}</p>)}</details>:null}</div>}
          {err && <p className="err" role="alert">{err}{ambiguous && <> <Link to="/runs" nav={nav} className="btn ghost">{en ? 'Check your requests' : 'これまでのお願いを確認する'}</Link></>}</p>}
          {problems.length > 0 && <div className="banner">{problems.map((p) => <div key={p.code} title={p.message}>{p.code === 'team_selection' ? p.message : friendlyProblem(p, getLang())}</div>)} {canConfigure && <Link to="/settings" nav={nav}>{t("設定へ")}</Link>}</div>}
          <div className="request-examples" aria-label={en ? 'Request ideas' : 'お願いの例'}>{(en ? ['Summarize my notes', 'Make a comparison table', 'Review my writing'] : ['資料を分かりやすくまとめて', '比較表をつくって', '文章をチェックして']).map((example, i) => <button type="button" key={example} disabled={busy || readOnly} onClick={() => { setGoal((en ? ['Use only the attached material to create guide.md: a short onboarding guide with prerequisites, first steps and limitations. Cite the source sections; mark anything unverified.', 'Use only the attached material to create comparison.md with a comparison table. Include source references and mark missing facts as unverified.', 'Review the attached writing and create review.md with suggested edits, reasons and unresolved questions.'] : ['添付した資料だけを使い、前提条件・最初の手順・制約をまとめた短い導入ガイド guide.md を作ってください。根拠の節を示し、確かめられない点は未確認と明記してください。', '添付した資料だけを使い、比較表 comparison.md を作ってください。根拠を添え、資料にない内容は未確認と明記してください。', '添付した文章を確認し、修正案・理由・未解決の疑問を review.md にまとめてください。'])[i]); goalRef.current?.focus() }}><span aria-hidden="true">{['📝','🔎','✏️'][i]}</span><span className="example-label">{example}</span></button>)}</div>
          <div className="request-disclosure" aria-label={en ? 'Before you start' : '実行前の確認'}>
            <strong>{en ? 'Where your material goes' : '依頼・資料の送信先'}</strong>
            {cfg?.execution_summary?.length ? <ul>{[...new Set(cfg.execution_summary.map(item => `${item.destination} · ${item.model}`))].map(item => <li key={item}>{item}</li>)}</ul> : <p>{en ? 'Destination is not available yet. Check the team settings before starting.' : '送信先はまだ取得できていません。実行前にチーム設定を確認してください。'}</p>}
            <p>{en ? 'The configured AI receives your request and material. Configured tools may read sources, write workspace files and run sandboxed checks. External changes require approval. Stopping cannot recall material already sent.' : '設定したAIに依頼と資料を送ります。許可されたツールは資料の参照、作業用ファイルの作成、隔離環境での検査を行います。外部の変更には承認が必要です。停止しても送信済みの資料は取り消せません。'}</p>
            <details><summary>{en ? 'Configured tool permissions' : '許可されているツール'}</summary><p>{[...new Set(cfg?.execution_summary?.flatMap(s => s.tools) || [])].join(' · ') || (en ? 'Not available' : '未取得')}</p></details>
          </div>
          <p className="muted small ask-draft"><span>{draftSaved ? (en ? 'Draft and attachments stay in this browser tab until sent or discarded.' : '下書きと添付資料は送信・破棄まで、このブラウザーのタブに保存します。') : (en ? 'Browser storage is unavailable. Navigation keeps the draft, but reloading will lose it.' : 'ブラウザーに保存できません。画面移動中は保持しますが、再読み込みすると失われます。')}</span> <button type="button" className="btn ghost" disabled={busy} onClick={() => { clearRequestDraft(); setGoal(''); setText(''); setUrls(''); setFiles([]); setBudget(''); setOutputPath(''); setDocumentWorkflow(false); setMinChars(''); setMaxChars(''); setExcludedPhrases(''); setAdaptiveTeam(true); setSelectedAgentIds(undefined) }}>{en ? 'Discard draft' : '下書きを破棄'}</button></p>
          {cfg && <p className="request-budget">{en ? 'Budget limit' : '予算上限'}: {money(budget && Number.isFinite(Number(budget)) && Number(budget)>0 ? Number(budget) : cfg.limits.budget_usd)} {en ? 'per request, estimated from configured prices; not a provider billing cap.' : '／1回。設定価格に基づく見積り上限です。提供元の請求上限ではありません。'}</p>}
        </form>
      </section>
      <section className="runs-list">
        <h2>{en ? "Your recent requests" : "これまでのお願い"}</h2>
        <Link to="/runs" nav={nav} className="btn ghost">{en ? "View all work by status →" : "状態別の作業一覧を見る →"}</Link>
        {runsFailed ? <p role="alert">{en ? 'Could not load earlier requests. Reload to try again.' : 'これまでのお願いを読み込めませんでした。再読み込みしてください。'}</p> : !loaded ? <p className="muted">{en ? 'Loading earlier requests…' : 'これまでのお願いを読み込んでいます…'}</p> : runs.length === 0 && <p className="muted">{t("まだ実行はありません。")}</p>}
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

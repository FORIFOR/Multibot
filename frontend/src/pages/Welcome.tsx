import { botName } from '../lib/journey'
import { useCallback, useEffect, useState } from 'react'
import BotAvatar from '../components/BotAvatar'
import { api, type Config } from '../lib/api'
import { getLang } from '../lib/i18n'
import { friendlyProblem, roleLabel, teamOrder } from '../lib/journey'
import { clampStep, markWelcomed, setDraftGoal, WELCOME_STEPS } from '../lib/welcome'
import '../journey.css'
import '../welcome.css'

/** First-visit introduction: request, data destination and results. Nothing starts here. */
export default function Welcome({ nav, canConfigure = true }: { nav: (p: string) => void; canConfigure?: boolean }) {
  const en = getLang() === 'en'
  const say = (ja: string, english: string) => (en ? english : ja)
  const [step, setStep] = useState(() => clampStep(Number(new URLSearchParams(window.location.search).get('step')) - 1))
  const [cfg, setCfg] = useState<Config | null>(null)
  const [failed, setFailed] = useState(false)
  const reload = useCallback(async () => { try { setCfg(await api.config()); setFailed(false) } catch { setFailed(true) } }, [])
  useEffect(() => { api.config().then(setCfg).catch(() => setFailed(true)) }, [])
  const go = (n: number) => { const next = clampStep(n); setStep(next); history.replaceState(history.state, '', `/welcome?step=${next + 1}`) }
  const finish = (goal?: string) => { markWelcomed(); if (goal) setDraftGoal(goal); nav('/') }

  const mates = teamOrder((cfg?.agents || []).filter(a => a.enabled).map(a => [a.id, a] as [string, typeof a]))
  const companion = mates.find(([, a]) => a.role === 'master')?.[1] || mates[0]?.[1]
  const lines: Record<string, [string, string]> = {
    master: ['お願いを聞いて、進め方と完了条件を決めます。', 'Listens to your request, then plans the work and the finish line.'],
    researcher: ['渡した資料や公開ページを読んで、根拠を集めます。', 'Reads your files and public pages to gather evidence.'],
    builder: ['ファイルを作り、指摘を受けたら直します。', 'Makes the files, and fixes them when a finding comes back.'],
    reviewer: ['完了条件を一つずつ確かめます。通さないこともあります。', 'Checks each finish condition. Sometimes the answer is no.'],
    reporter: ['できたことと、まだ確かめていないことを伝えます。', 'Reports what was done and what is still unverified.'],
  }
  const titles: [string, string][] = [['資料から、使うファイルへ', 'From your material to a file'], canConfigure ? ['AIと送信先を確認する', 'Check the model and destination'] : ['資料の送信先を確認する', 'Know where your material goes'], ['最初のお願い', 'Your first request']]
  const leads: [string, string][] = [
    ['資料を添えてお願いすると、チームがファイルを作り、確認の記録と一緒に渡します。中身を読んで、使う版を選び、保存できます。', 'Attach your material and ask for a file. The team creates it with a check record. Read the result, choose a version and save it.'],
    canConfigure ? ['依頼と資料は、設定したAIで処理します。モデルの送信先と、許可したツールを実行前に確認してください。', 'The configured AI processes your request and material. Check its destination and allowed tools before starting.'] : ['運営者が用意したAIを使います。接続の設定は不要です。依頼する前に、資料の送信先を確認してください。', 'Use the AI prepared by the service administrator. No model setup is needed. Check where your material will be sent before starting.'],
    ['例を選ぶと、入力欄に入ります。自動では始まりません。', 'Pick an example to fill the request box. Nothing starts automatically.'],
  ]
  const examples: [string, string][] = [
    ['この資料を、要点3つと次にやることにまとめて。', 'Summarise these notes into three key points and next actions.'],
    ['このCSVを月別に集計する小さなツールを作って。使い方とテストも付けて。', 'Build a small tool that totals this CSV by month, with usage notes and tests.'],
    ['この文章を読みやすく直して。変えた箇所と理由も教えて。', 'Make this text easier to read, and tell me what you changed and why.'],
  ]
  const ready = cfg ? cfg.problems.length === 0 : false
  const conn = cfg?.connections.find(c => c.id === cfg.defaults.connection_id)

  return (
    <div className="welcome">
      <aside className="welcome-side">
        <p className="welcome-step">{say('はじめに', 'SETUP')} · {String(step + 1).padStart(2, '0')} / {String(WELCOME_STEPS).padStart(2, '0')}</p>
        <h1>{say(titles[step][0], titles[step][1])}</h1>
        <p className="welcome-lead">{say(leads[step][0], leads[step][1])}</p>
        <div className="welcome-companion">{companion && <BotAvatar id={companion.id} role={companion.role} emoji={companion.emoji} name={companion.display_name || botName(companion.role, getLang())} state={step === 1 && !ready ? 'waiting' : 'idle'} size="stage" />}</div>
      </aside>
      <section className="welcome-main" aria-live="polite">
        <ol className="welcome-dots" aria-label={say('進み具合', 'Progress')}>{titles.map((t, i) => <li key={i} aria-current={i === step ? 'step' : undefined}><button type="button" onClick={() => go(i)} aria-label={`${i + 1}. ${say(t[0], t[1])}`} /></li>)}</ol>
        {failed && <p className="work-warning" role="alert">{say('受付状況を確認できませんでした。', 'Could not check service availability.')} <button type="button" className="btn ghost" onClick={reload}>{say('もう一度確認する', 'Check again')}</button></p>}
        {step === 0 && <ul className="welcome-mates">{mates.filter(([,a])=>a.role==='master').map(([id, a]) => (
          <li key={id}><BotAvatar id={id} role={a.role} emoji={a.emoji} name={a.display_name || botName(a.role, getLang())} state="idle" />
            <div><h2>{a.display_name || botName(a.role, getLang())}</h2><p>{say(...(lines[a.role] || ['あなたが作った、専門の仲間です。', 'A specialist teammate you created.']))}</p></div></li>))}</ul>}
        {step === 0 && <div className="welcome-roles">
          {/* Roles, not specific bots: the coordinator picks who joins each request. Makers and checkers stay separate. */}
          <h2>{say('依頼に合わせて加わる係', 'Who joins, depending on the request')}</h2>
          <ul>{(['researcher', 'builder', 'reviewer', 'reporter'] as const).map(role => <li key={role}><strong>{roleLabel(role, getLang())}</strong><span>{say(...lines[role])}</span></li>)}</ul>
          <p className="muted small">{say('チームで進めるときは、つくる係と確かめる係を別の仲間が担当します。', 'When the team works on a request, one teammate makes the files and a different one checks them.')}</p>
          <p className="muted small">{say('確認はAIによる記録です。内容の正確性は保証されません。未確認や要修正の項目を見て、使う前にご自身でも確認してください。', 'Checks are records of AI review, not a guarantee of accuracy. Read unverified or flagged items and inspect the result before using it.')}</p>
        </div>}
        {step === 1 && <div className="welcome-connect">
          <div className={`welcome-status ${ready ? 'ok' : 'todo'}`} role="status">
            <strong>{failed ? say('受付状況を確認できません', 'Availability could not be checked') : !cfg ? say('受付状況を確認しています…', 'Checking availability…') : ready ? say('接続の準備ができています', 'The connection is ready') : canConfigure ? say('接続の確認が必要です', 'The connection needs checking') : say('運営者による確認が必要です', 'The service administrator needs to check preparation')}</strong>
            {canConfigure && conn && <p><span className="mono">{conn.driver}</span> · <span className="mono">{cfg?.defaults.model}</span></p>}
            {!ready && cfg && (canConfigure ? <ul>{cfg.problems.slice(0, 4).map((p, i) => <li key={i} title={p.message}>{friendlyProblem(p, getLang())}</li>)}</ul> : <p>{say('現在、お願いを受け付ける準備が整っていません。時間をおいて再確認するか、運営者にお問い合わせください。', 'Requests are not available yet. Check again later or contact the service administrator.')}</p>)}
            {cfg?.execution_summary?.length ? <ul>{[...new Set(cfg.execution_summary.map(item => `${item.destination} · ${item.model}`))].map(destination => <li key={destination}>{destination}</li>)}</ul> : null}
            {!ready && cfg && <button type="button" className="btn ghost" onClick={reload}>{say('受付状況を再確認', 'Check availability again')}</button>}
          </div>
          <ul className="welcome-facts">
            <li>{say('送信した資料・実行記録・成果物は、Agent Teamが動いているサーバーに保存します。', 'Submitted material, work records and files are stored on the server running Agent Team.')}</li>
            <li>{say('依頼と資料は、表示された接続先のAIに送られます。ローカルモデルでも、許可されたツールは外部へ通信する場合があります。', 'Your request and material go to the displayed AI destination. Even with a local model, allowed tools may communicate externally.')}</li>
            <li>{say('開始前に送信先・許可された操作・予算上限を確認できます。停止しても、すでに送信した資料は取り消せません。', 'Check the destination, allowed actions and budget before starting. Stopping cannot recall material already sent.')}</li>
          </ul>
          {canConfigure && <button type="button" className="btn ghost" onClick={() => { markWelcomed(); nav('/settings') }}>{ready ? say('接続を変える', 'Change the connection') : say('接続を設定する', 'Set up the connection')}</button>}
        </div>}
        {step === 2 && <div className="welcome-examples">{examples.map(([ja, english]) => <button type="button" key={ja} onClick={() => finish(say(ja, english))}>{say(ja, english)}<span aria-hidden="true">→</span></button>)}
          <button type="button" className="welcome-blank" onClick={() => finish()}>{say('自分の言葉で書く', 'Write my own')}</button></div>}
        <footer className="welcome-foot">
          {step > 0 ? <button type="button" className="btn ghost" onClick={() => go(step - 1)}>← {say('戻る', 'Back')}</button> : <button type="button" className="btn ghost" onClick={() => finish()}>{say('あとで見る', 'Skip')}</button>}
          {step < WELCOME_STEPS - 1 && <button type="button" className="btn signal" onClick={() => go(step + 1)}>{say('続ける', 'Continue')} →</button>}
        </footer>
      </section>
    </div>
  )
}

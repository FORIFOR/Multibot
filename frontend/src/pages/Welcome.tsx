import { useEffect, useState } from 'react'
import BotAvatar from '../components/BotAvatar'
import { api, type Config } from '../lib/api'
import { getLang } from '../lib/i18n'
import { friendlyProblem, roleLabel, teamOrder } from '../lib/journey'
import { clampStep, markWelcomed, setDraftGoal, WELCOME_STEPS } from '../lib/welcome'
import '../journey.css'
import '../welcome.css'

/** First-visit introduction: meet the team, check the AI connection, pick a first request. Nothing starts here. */
export default function Welcome({ nav, canConfigure = true }: { nav: (p: string) => void; canConfigure?: boolean }) {
  const en = getLang() === 'en'
  const say = (ja: string, english: string) => (en ? english : ja)
  const [step, setStep] = useState(() => clampStep(Number(new URLSearchParams(window.location.search).get('step')) - 1))
  const [cfg, setCfg] = useState<Config | null>(null)
  const [failed, setFailed] = useState(false)
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
  const titles: [string, string][] = [['チームを紹介します', 'Meet your team'], ['AIにつなぐ', 'Connect a model'], ['最初のお願い', 'Your first request']]
  const leads: [string, string][] = [
    ['聞く、分ける、任せる、確かめて渡す。まとめ役があなたとチームの間に立ちます。', 'Listen, split, delegate, check and hand back. The coordinator stands between you and the team.'],
    ['チームは、あなたが選んだAIで動きます。ローカルのAIなら、入力は外へ出ません。', 'The team runs on the model you choose. With a local model, your input never leaves.'],
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
        <div className="welcome-companion">{companion && <BotAvatar id={companion.id} role={companion.role} emoji={companion.emoji} name={companion.display_name || roleLabel(companion.role, getLang())} state={step === 1 && !ready ? 'waiting' : 'idle'} size="stage" />}</div>
      </aside>
      <section className="welcome-main" aria-live="polite">
        <ol className="welcome-dots" aria-label={say('進み具合', 'Progress')}>{titles.map((t, i) => <li key={i} aria-current={i === step ? 'step' : undefined}><button type="button" onClick={() => go(i)} aria-label={`${i + 1}. ${say(t[0], t[1])}`} /></li>)}</ol>
        {failed && <p className="work-warning" role="alert">{say('チームの設定を読み込めませんでした。再読み込みしてください。', 'Could not load the team settings. Reload to try again.')}</p>}
        {step === 0 && <ul className="welcome-mates">{mates.map(([id, a]) => (
          <li key={id}><BotAvatar id={id} role={a.role} emoji={a.emoji} name={a.display_name || roleLabel(a.role, getLang())} state="idle" />
            <div><h2>{a.display_name || roleLabel(a.role, getLang())}</h2><p>{say(...(lines[a.role] || ['あなたが作った、専門の仲間です。', 'A specialist teammate you created.']))}</p></div></li>))}</ul>}
        {step === 1 && <div className="welcome-connect">
          <div className={`welcome-status ${ready ? 'ok' : 'todo'}`} role="status">
            <strong>{ready ? say('接続は確認済みです', 'The connection is verified') : say('接続の確認が必要です', 'The connection needs checking')}</strong>
            {conn && <p><span className="mono">{conn.driver}</span> · <span className="mono">{cfg?.defaults.model}</span></p>}
            {!ready && cfg && <ul>{cfg.problems.slice(0, 4).map((p, i) => <li key={i} title={p.message}>{friendlyProblem(p, getLang())}</li>)}</ul>}
          </div>
          <ul className="welcome-facts">
            <li>{say('実行記録とファイルは、このPCに保存します。', 'The work record and files stay on this computer.')}</li>
            <li>{say('クラウドのAIを選んだ場合は、入力がその接続先へ送られます。', 'If you choose a cloud model, your input goes to that provider.')}</li>
            <li>{say('外部への投稿や送信はしません。作るのは草案までです。', 'Nothing is posted or sent externally. It stops at drafts.')}</li>
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

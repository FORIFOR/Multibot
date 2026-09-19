import { useEffect, useRef, useState, type FormEvent } from 'react'
import { api, ApiError, type AgentSpec, type Config } from '../lib/api'
import { getLang } from '../lib/i18n'
import { isBotEmoji } from '../lib/bot-identity'
import BotAvatar from './BotAvatar'
import { roleLabel } from '../lib/journey'

export default function BotSettingsCard({ a, cfg, refresh }: { a: AgentSpec; cfg: Config; refresh: () => Promise<Config> }) {
  const en = getLang() === 'en'
  const l = (ja: string, english: string) => en ? english : ja
  const effective = cfg.effective_agents[a.id]
  const displayName = a.display_name || roleLabel(a.role, getLang())
  const [name, setName] = useState(a.display_name || '')
  const [emoji, setEmoji] = useState(a.emoji || '')
  const [prompt, setPrompt] = useState(effective?.system_prompt || '')
  const [connection, setConnection] = useState(a.connection_id)
  const [model, setModel] = useState(a.model)
  const [effort, setEffort] = useState(a.effort || '')
  const [locked, setLocked] = useState(a.prompt_mode === 'user_locked')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [note, setNote] = useState('')
  const pending = useRef(false)
  useEffect(() => { setName(a.display_name || ''); setEmoji(a.emoji || '') }, [a.display_name, a.emoji])
  useEffect(() => { setPrompt(effective?.system_prompt || '') }, [effective?.system_prompt])
  useEffect(() => { setConnection(a.connection_id); setModel(a.model); setEffort(a.effort || ''); setLocked(a.prompt_mode === 'user_locked') }, [a.connection_id, a.model, a.effort, a.prompt_mode])
  const dirty = name !== (a.display_name || '') || emoji !== (a.emoji || '') || prompt !== (effective?.system_prompt || '') || connection !== a.connection_id || model !== a.model || effort !== (a.effort || '') || locked !== (a.prompt_mode === 'user_locked')
  const validEmoji = !emoji.trim() || isBotEmoji(emoji)
  const patch = async (body: Record<string, unknown>, message: string) => {
    if (pending.current) return
    pending.current = true; setBusy(true); setError(''); setNote('')
    try {
      await api.patchAgent(a.id, { expected_revision: cfg.revision, ...body })
      setNote(message)
      try { await refresh() } catch { setError(l('保存は完了しました。ページを再読み込みして最新設定を確認してください。', 'Saved. Reload the page to see the latest settings.')) }
    } catch (e) {
      setError(e instanceof ApiError && e.status === 409 ? l('別の場所で設定が更新されました。入力は残しています。最新設定を読み込み、確認して再保存してください。', 'Settings changed elsewhere. Your edits are preserved. Reload settings, review, then save again.') : l('保存できませんでした。入力は残しています。再試行してください。', 'Could not save. Your edits are preserved; please retry.'))
    } finally { pending.current = false; setBusy(false) }
  }
  const save = (event: FormEvent) => {
    event.preventDefault()
    if (!validEmoji || !dirty) return
    const body: Record<string, unknown> = { display_name: name.trim(), emoji: emoji.trim(), connection_id: connection, model: model.trim() || 'inherit', effort, prompt_mode: locked ? 'user_locked' : 'auto_seed' }
    if (prompt !== effective?.system_prompt) body.system_prompt_override = prompt
    void patch(body, l('保存しました。次の依頼から反映されます。', 'Saved. Changes apply to your next request.'))
  }
  return (
    <article className="agentcard bot-settings-card" id={`agent-card-${a.id}`} tabIndex={-1} aria-label={displayName} aria-busy={busy}>
      <header>
        <BotAvatar id={a.id} role={a.role} name={displayName} emoji={a.emoji} state={a.enabled ? 'idle' : 'disabled'} />
        <div className="bot-settings-title"><h3>{displayName}</h3><span className="muted small">{roleLabel(a.role, getLang())}</span></div>
        <button className="bot-toggle" type="button" role="switch" aria-checked={a.enabled} aria-label={l(`${displayName}をチームで使う`, `Enable ${displayName}`)} disabled={busy} onClick={() => void patch({ enabled: !a.enabled }, l('参加設定を保存しました。', 'Participation updated.'))}>
          <span className={'switch' + (a.enabled ? ' on' : '')} aria-hidden="true" /><span>{a.enabled ? l('参加中', 'Enabled') : l('お休み', 'Disabled')}</span>
        </button>
      </header>
      <form onSubmit={save}>
        <fieldset className="bot-card-fields" disabled={busy}>
          <legend className="sr-only">{l('Botの設定', 'Bot settings')}</legend>
          <div className="bot-identity-grid">
            <label className="bot-field">{l('名前', 'Name')}<input className="input" value={name} onChange={e => setName(e.target.value)} maxLength={40} placeholder={displayName} /></label>
            <label className="bot-field">{l('絵文字', 'Emoji')}<input className="input bot-emoji-input" value={emoji} maxLength={64} onChange={e => setEmoji(e.target.value)} placeholder="🤖" aria-invalid={!validEmoji} aria-describedby={`emoji-note-${a.id}`} /></label>
          </div>
          <small className={!validEmoji ? 'err' : 'muted'} id={`emoji-note-${a.id}`}>{l('絵文字を1つ。空欄にすると元のキャラクターに戻ります。', 'Use one emoji, or leave blank to restore the original character.')}</small>
          <details className="bot-advanced"><summary>{l('任せる仕事・モデル・詳細設定', 'Instructions, model & advanced settings')}</summary>
            <div className="stack">
              <label className="bot-field">{l('任せたいこと（システムプロンプト）', 'Instructions (system prompt)')}<textarea className="input" value={prompt} onChange={e => setPrompt(e.target.value)} maxLength={20000} /></label>
              <label className="bot-check"><input type="checkbox" checked={locked} onChange={e => setLocked(e.target.checked)} />{l('この指示を固定する', 'Keep these instructions locked')}</label>
              <div className="grid">
                <label className="bot-field">{l('API接続', 'Connection')}<select className="input" value={connection} onChange={e => setConnection(e.target.value)}><option value="inherit">{l('チームの共通設定', 'Team default')} ({cfg.defaults.connection_id})</option>{cfg.connections.map(c => <option key={c.id}>{c.id}</option>)}</select></label>
                <label className="bot-field">{l('モデル', 'Model')}<input className="input" value={model} onChange={e => setModel(e.target.value)} placeholder="inherit" /></label>
                <label className="bot-field">{l('推論の深さ', 'Reasoning effort')}<select className="input" value={effort} onChange={e => setEffort(e.target.value)}>{['', 'low', 'medium', 'high', 'xhigh', 'max'].map(v => <option key={v} value={v}>{v || l('既定', 'Default')}</option>)}</select></label>
              </div>
              <p className="muted small">ID: {a.id} · {effective?.model || '—'} · {effective?.driver || '—'}</p>
              <p className="muted small">Skills: {a.skill_ids.join(', ') || '—'} · Tools: {a.tools.length}</p>
              <button className="btn ghost" type="button" disabled={busy || a.system_prompt_override == null} onClick={() => void patch({ reset_prompt: true }, l('同梱の指示に戻しました。', 'Restored the bundled instructions.'))}>{l('同梱の指示に戻す', 'Restore bundled instructions')}</button>
            </div>
          </details>
          <div className="bot-card-actions"><button className="btn signal" disabled={!dirty || busy || !validEmoji} type="submit">{busy ? l('保存中…', 'Saving…') : l('変更を保存', 'Save changes')}</button>{dirty && <span className="muted small">{l('未保存の変更があります', 'Unsaved changes')}</span>}</div>
        </fieldset>
      </form>
      {note && <p className="bot-save-note" role="status">{note}</p>}
      {error && <div role="alert" className="bot-form-error">{error}<button type="button" className="btn ghost" disabled={busy} onClick={() => refresh().catch(() => setError(l('最新設定を読み込めませんでした。', 'Could not reload settings.')))}>{l('最新設定を読む', 'Reload settings')}</button></div>}
    </article>
  )
}

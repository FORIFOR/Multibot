import { useLayoutEffect, useRef, useState, type FormEvent } from 'react'
import { api, ApiError, type Config } from '../lib/api'
import { getLang } from '../lib/i18n'
import { EMOJI_CHOICES, isBotEmoji, newBotId } from '../lib/bot-identity'

export default function CustomBotCreator({ cfg, refresh }: { cfg: Config; refresh: () => Promise<Config> }) {
  const en = getLang() === 'en'
  const l = (ja: string, english: string) => en ? english : ja
  const [open, setOpen] = useState(false)
  const [id, setId] = useState(newBotId)
  const [name, setName] = useState('')
  const [emoji, setEmoji] = useState('🦊')
  const [prompt, setPrompt] = useState('')
  const [role, setRole] = useState('specialist')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [created, setCreated] = useState<{ id: string; name: string; emoji: string } | null>(null)
  const inFlight = useRef(false)
  const nameRef = useRef<HTMLInputElement>(null)
  // Set the initial focus during the opening commit. A deferred animation-frame
  // focus can steal typing from an emoji input the user has already selected.
  useLayoutEffect(() => { if (open) nameRef.current?.focus() }, [open])
  const validEmoji = isBotEmoji(emoji)
  const validId = /^[a-z][a-z0-9_-]{1,31}$/.test(id)
  const valid = validEmoji && validId && name.trim().length > 0 && prompt.trim().length > 0

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (inFlight.current || !valid) return
    inFlight.current = true; setBusy(true); setError('')
    const identity = { id, name: name.trim(), emoji: emoji.trim() }
    try {
      await api.createAgent({ expected_revision: cfg.revision, id, display_name: identity.name,
        emoji: identity.emoji, role, system_prompt: prompt.trim() })
      // The save succeeded. Never report it as failed just because the subsequent reload fails.
      setCreated(identity); setName(''); setPrompt(''); setEmoji('🦊'); setId(newBotId()); setRole('specialist'); setOpen(false)
      try { await refresh() }
      catch { setError(l('作成は完了しました。チーム一覧の更新に失敗しました。ページを再読み込みしてください。', 'Bot created. Reload the page to update your team list.')) }
      requestAnimationFrame(() => document.getElementById('custom-bot-created')?.focus())
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        try { await refresh() } catch { /* Keep the draft even when the refresh fails. */ }
        setError(l('設定が更新されたか、同じIDが使われています。入力は残しています。確認して再試行してください。', 'Settings changed or this ID is taken. Your draft is preserved; review and retry.'))
      } else setError(l('作成できませんでした。入力は残しています。再試行してください。', 'Could not create your bot. Your draft is preserved; please retry.'))
    } finally { inFlight.current = false; setBusy(false) }
  }
  const focusCreated = () => {
    if (!created) return
    const card = document.getElementById(`agent-card-${created.id}`)
    card?.scrollIntoView({ block: 'center', behavior: 'auto' }); card?.focus()
  }
  return (
    <section className="custom-bot-maker" aria-label={l('自分だけのBot', 'Your own bot')}>
      <button className="custom-bot-add" type="button" aria-expanded={open} aria-controls="custom-bot-form" disabled={busy} onClick={() => {
        setOpen(!open); setError('')
      }}>
        <span className="custom-bot-add-face" aria-hidden="true">✨</span>
        <span><b>{l('自分だけのBotをつくる', 'Create your own bot')}</b><small>{l('好きな絵文字と名前で、あなたのチームに。', 'A familiar face. A name you love. Your teammate.')}</small></span>
        <span className="custom-bot-plus" aria-hidden="true">{open ? '−' : '+'}</span>
      </button>
      {created && <div className="bot-created" id="custom-bot-created" tabIndex={-1} role="status">
        <span aria-hidden="true">{created.emoji}</span>
        <div><b>{l(`${created.name}がチームに加わりました`, `${created.name} joined your team`)}</b><p>{l('次の依頼から参加できます。モデルはチームの共通設定を使います。', 'Available for your next request using the team’s default model.')}</p>
          <button className="btn ghost" type="button" onClick={focusCreated}>{l('このBotを見る', 'View this bot')}</button>
        </div>
      </div>}
      {error && <p className="bot-form-error" role="alert">{error}</p>}
      {open && <form id="custom-bot-form" className="custom-bot-form" onSubmit={submit} aria-busy={busy}>
        <fieldset disabled={busy} className="bot-form-fields">
          <legend className="sr-only">{l('Botを作成', 'Create a bot')}</legend>
          <div className="custom-bot-preview" aria-label={l('Botのプレビュー', 'Bot preview')}>
            <span className="custom-bot-preview-face" aria-hidden="true">{validEmoji ? emoji : '🤖'}</span>
            <div><b>{name.trim() || l('あなたの相棒', 'Your teammate')}</b><span className="custom-bot-preview-caption">{l('どんな仕事を一緒にしよう？', 'What shall we work on together?')}</span></div>
          </div>
          <fieldset className="emoji-field"><legend>{l('好きな絵文字', 'Favorite emoji')}</legend>
            <div className="emoji-picker">
              {EMOJI_CHOICES.map(([item, ja, english]) => <button type="button" key={item} aria-label={en ? english : ja} aria-pressed={emoji === item} className={emoji === item ? 'active' : ''} onClick={() => setEmoji(item)}>{item}</button>)}
            </div>
            <label className="emoji-free-input">{l('ほかの絵文字を使う', 'Use another emoji')}<input className="input bot-emoji-input" aria-describedby="emoji-help" aria-invalid={!validEmoji} value={emoji} onChange={e => setEmoji(e.target.value)} maxLength={64} required autoComplete="off" /></label>
            <small id="emoji-help" className={!validEmoji ? 'err' : 'muted'}>{l('絵文字を1つ選んでください。旗や肌の色つきの絵文字も使えます。', 'Choose one emoji. Flags and skin-tone sequences work too.')}</small>
          </fieldset>
          <label className="bot-field"><span>{l('名前', 'Name')}</span><input ref={nameRef} className="input" value={name} onChange={e => setName(e.target.value)} maxLength={40} required placeholder={l('例：リサーチ狐', 'e.g. Research Fox')} autoComplete="off" /></label>
          <label className="bot-field"><span>{l('任せたいこと', 'What should this bot do?')}</span><textarea className="input" value={prompt} onChange={e => setPrompt(e.target.value)} maxLength={20000} required placeholder={l('例：資料を読み、重要なポイントをやさしい日本語でまとめて。わからないことは推測せずに教えて。', 'e.g. Read the source material and summarize the important points clearly. Flag anything uncertain.')} /></label>
          <details className="bot-advanced"><summary>{l('詳細設定（任意）', 'Advanced settings (optional)')}</summary>
            <div className="stack">
              <label className="bot-field">{l('役割', 'Role')}<select className="input" value={role} onChange={e => setRole(e.target.value)}>
                <option value="specialist">{l('おまかせ・専門家', 'General specialist')}</option><option value="designer">{l('デザイン', 'Design')}</option><option value="editor">{l('文章・編集', 'Writing & editing')}</option><option value="analyst">{l('分析', 'Analysis')}</option><option value="translator">{l('翻訳', 'Translation')}</option>
              </select></label>
              <label className="bot-field">{l('管理用ID（自動生成）', 'Internal ID (generated)')}<input className="input" value={id} maxLength={32} onChange={e => setId(e.target.value)} aria-invalid={!validId} pattern="[a-z][a-z0-9_\-]{1,31}" /></label>
              {!validId && <small className="err">{l('英小文字で始まる2〜32文字の英数字・ハイフン・アンダースコアにしてください。', 'Use 2–32 lowercase letters, numbers, underscores or hyphens; start with a letter.')}</small>}
              <p className="muted small">{l('モデル・API接続は共通設定を引き継ぎます。作成後に変更できます。', 'Model and connection inherit the team defaults. You can change them after creation.')}</p>
            </div>
          </details>
          <div className="bot-form-actions"><button className="btn signal" type="submit" disabled={busy || !valid}>{busy ? l('チームに追加中…', 'Adding to your team…') : l('このBotをつくる', 'Create this bot')}</button><button type="button" className="btn ghost" disabled={busy} onClick={() => setOpen(false)}>{l('キャンセル', 'Cancel')}</button></div>
          <p className="muted small">{l('作成だけではAIの呼び出しや課金は発生しません。', 'Creating a bot does not call an AI model or incur model charges.')}</p>
        </fieldset>
      </form>}
    </section>
  )
}

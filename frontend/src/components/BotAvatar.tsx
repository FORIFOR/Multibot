import { getLang } from '../lib/i18n'
import { botKind, botStateLabel, type BotVisualState } from '../lib/bot-presentation'

export default function BotAvatar({ id, role, emoji, name, state = 'idle', size = 'chat' }: {
  id: string; role?: string; emoji?: string | null; name?: string | null;
  state?: BotVisualState; size?: 'micro' | 'chat' | 'card' | 'stage'
}) {
  const kind = botKind(id, role)
  const face = state === 'done' ? 'happy' : ['blocked', 'approval'].includes(state) ? 'worried' : ['thinking', 'reviewing'].includes(state) ? 'focus' : 'normal'
  const accessory = { master: 'crown', researcher: 'lens', builder: 'pencil', reviewer: 'check', reporter: 'page', helper: 'spark' }[kind]
  // The badge says the state with a symbol as well as a colour: three moving dots while working.
  const working = ['thinking', 'researching', 'building', 'reviewing'].includes(state)
  const glyph = ({ done: '✓', blocked: '!', approval: '?', stopped: 'Ⅱ', disabled: 'z', waiting: '…' } as Partial<Record<BotVisualState, string>>)[state]
  const label = `${name || id} · ${botStateLabel(state, getLang())}`
  return (
    <span className={`bot-character bot-${kind} bot-${state} bot-size-${size}${emoji ? ' bot-custom' : ''}`} data-bot-state={state} role="img" aria-label={label} title={label}>
      {emoji ? <span className="bot-custom-emoji" aria-hidden="true">{emoji}</span> : <>
        <span className="bot-antenna" aria-hidden="true"><i /></span>
        <span className="bot-head" aria-hidden="true">
          <span className={`bot-face face-${face}`}><i className="eye left" /><i className="eye right" /><i className="mouth" /></span>
          <span className={`bot-accessory accessory-${accessory}`} />
        </span>
        <span className="bot-body" aria-hidden="true"><i className="bot-heart" /></span>
      </>}
      <span className={`bot-state-mark${working ? ' is-working' : ''}`} aria-hidden="true">{working ? <><i /><i /><i /></> : glyph}</span>
    </span>
  )
}

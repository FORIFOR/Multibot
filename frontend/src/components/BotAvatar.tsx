import { getLang } from '../lib/i18n'
import { botKind, botStateLabel, type BotVisualState } from '../lib/bot-presentation'

export default function BotAvatar({ id, role, emoji, name, state = 'idle', size = 'chat' }: {
  id: string; role?: string; emoji?: string | null; name?: string | null;
  state?: BotVisualState; size?: 'micro' | 'chat' | 'card' | 'stage'
}) {
  const kind = botKind(id, role)
  const icon = emoji?.trim() || { master: '🧭', researcher: '🔎', builder: '🛠️', reviewer: '✅', reporter: '📝', helper: '🤖' }[kind]
  // The badge says the state with a symbol as well as a colour: three moving dots while working.
  const working = ['thinking', 'researching', 'building', 'reviewing'].includes(state)
  const glyph = ({ done: '✓', blocked: '!', approval: '?', stopped: 'Ⅱ', disabled: 'z', waiting: '…' } as Partial<Record<BotVisualState, string>>)[state]
  const label = `${name || id} · ${botStateLabel(state, getLang())}`
  return (
    <span className={`bot-character bot-${kind} bot-${state} bot-size-${size} bot-custom`} data-bot-state={state} role="img" aria-label={label} title={label}>
      <span className="bot-custom-emoji" aria-hidden="true">{icon}</span>
      <span className={`bot-state-mark${working ? ' is-working' : ''}`} aria-hidden="true">{working ? <><i /><i /><i /></> : glyph}</span>
    </span>
  )
}

import { getLang } from '../lib/i18n'
import { botKind, botStateLabel, type BotVisualState } from '../lib/bot-presentation'
import { BOT_SHAPES, BOT_TOOL, botFace, facePaths } from '../lib/bot-shapes'

/** Every teammate is its role's shape with a face; the face follows the state.
 *  A chosen emoji is kept as the teammate's badge; without one, the role's tool is shown. */
export default function BotAvatar({ id, role, emoji, name, state = 'idle', size = 'chat' }: {
  id: string; role?: string; emoji?: string | null; name?: string | null;
  state?: BotVisualState; size?: 'micro' | 'chat' | 'card' | 'stage'
}) {
  const kind = botKind(id, role)
  const shape = BOT_SHAPES[kind]
  const face = facePaths(botFace(state), shape.dy)
  const badge = emoji?.trim() || BOT_TOOL[kind]
  // The mark says the state with a symbol as well as a colour: three moving dots while working.
  const working = ['thinking', 'researching', 'building', 'reviewing'].includes(state)
  const glyph = ({ done: '✓', blocked: '!', approval: '?', stopped: 'Ⅱ', disabled: 'z', waiting: '…' } as Partial<Record<BotVisualState, string>>)[state]
  const label = `${name || id} · ${botStateLabel(state, getLang())}`
  return (
    <span className={`bot-character bot-${kind} bot-${state} bot-size-${size} bot-shape`} data-bot-state={state} role="img" aria-label={label} title={label}>
      <svg className="bot-shape-art" viewBox="-6 -6 112 112" aria-hidden="true" focusable="false">
        <path d={shape.body} fill={shape.fill} stroke={shape.fill} strokeWidth={8} strokeLinejoin="round" />
        {face.eyes && <path d={face.eyes} fill="#1b1a17" />}
        <path d={face.line} fill="none" stroke="#1b1a17" strokeWidth={3.5} strokeLinecap="round" />
        {face.drop && <path className="bot-shape-drop" d={face.drop} fill="#6fa3d6" />}
      </svg>
      <span className="bot-shape-badge" aria-hidden="true">{badge}</span>
      <span className={`bot-state-mark${working ? ' is-working' : ''}`} aria-hidden="true">{working ? <><i /><i /><i /></> : glyph}</span>
    </span>
  )
}

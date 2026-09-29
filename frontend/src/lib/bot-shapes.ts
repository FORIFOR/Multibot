/** Default teammate characters (design "1b かたち", 2026-09-29): one flat shape per role with a face.
 *  Pure data, no asset imports, so Node unit tests and the site build can use it. Only the face changes with state. */
import type { BotKind, BotVisualState } from './bot-presentation'

export type BotFace = 'idle' | 'working' | 'done' | 'trouble'
export const BOT_SHAPES: Record<BotKind, { body: string; fill: string; dy: number }> = {
  master: { body: 'M14 58a36 36 0 1 0 72 0a36 36 0 1 0 -72 0', fill: '#eca86a', dy: 0 },
  researcher: { body: 'M50 14l40 72h-80z', fill: '#d9c25a', dy: 12 },
  builder: { body: 'M16 24h68v68h-68z', fill: '#ee9a86', dy: 0 },
  reviewer: { body: 'M50 10l40 46l-40 40l-40 -40z', fill: '#8fb4ee', dy: -2 },
  reporter: { body: 'M14 90v-32a36 36 0 0 1 72 0v32z', fill: '#e59bcf', dy: 0 },
  helper: { body: 'M50 20l32 18v36l-32 18l-32 -18v-36z', fill: '#86c99a', dy: 0 },
}
/** Role tool shown as a small badge when the user has not chosen an emoji. */
export const BOT_TOOL: Record<BotKind, string> = { master: '📋', researcher: '🔎', builder: '🛠️', reviewer: '✅', reporter: '📝', helper: '🤝' }

export function botFace(state: BotVisualState): BotFace {
  if (['thinking', 'researching', 'building', 'reviewing'].includes(state)) return 'working'
  if (state === 'done') return 'done'
  if (state === 'blocked' || state === 'approval') return 'trouble'
  return 'idle'
}
const dot = (x: number, y: number, r = 4.2) => `M${x - r} ${y}a${r} ${r} 0 1 0 ${r * 2} 0a${r} ${r} 0 1 0 ${-r * 2} 0`
/** eyes = filled path, line = stroked path, drop = small blue mark (sweat drop / working dots). */
export function facePaths(face: BotFace, dy: number): { eyes: string; line: string; drop: string } {
  switch (face) {
    case 'working': return { eyes: dot(45, 56 + dy, 3.8) + dot(63, 56 + dy, 3.8), line: `M49 ${68 + dy}h6`, drop: dot(70, 30 + dy, 2.6) + dot(78, 26 + dy, 2.6) + dot(86, 22 + dy, 2.6) }
    case 'done': return { eyes: '', line: `M36 ${59 + dy}q5 -6 10 0M54 ${59 + dy}q5 -6 10 0M45 ${66 + dy}q5 5 10 0`, drop: '' }
    case 'trouble': return { eyes: '', line: `M36 ${58 + dy}h9M55 ${58 + dy}h9M45 ${69 + dy}q5 -3.5 10 0`, drop: `M74 ${36 + dy}q5 7 0 10q-5 -3 0 -10z` }
    default: return { eyes: dot(41, 58 + dy) + dot(59, 58 + dy), line: `M46 ${67 + dy}q4 3.5 8 0`, drop: '' }
  }
}
/** Standalone SVG of the idle character; the same markup as frontend/src/assets/bots/*.svg. */
export function botSvg(kind: BotKind): string {
  const s = BOT_SHAPES[kind], f = facePaths('idle', s.dy)
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="-6 -6 112 112"><path d="${s.body}" fill="${s.fill}" stroke="${s.fill}" stroke-width="8" stroke-linejoin="round"/><path d="${f.eyes}" fill="#1b1a17"/><path d="${f.line}" fill="none" stroke="#1b1a17" stroke-width="3.5" stroke-linecap="round"/></svg>\n`
}

/** Pure view state: never infer live activity from task wording or old messages. */
export type BotVisualState = 'idle' | 'waiting' | 'thinking' | 'researching' | 'building' | 'reviewing' | 'done' | 'blocked' | 'approval' | 'stopped' | 'disabled'
export type BotKind = 'master' | 'researcher' | 'builder' | 'reviewer' | 'reporter' | 'helper'
type Task = { status: string }
/** The emoji shown for a teammate (badge, pickers, plain-text places): the one the user chose, or its role's tool. */
export function botIcon(id: string, role?: string, emoji?: string | null): string {
  return emoji?.trim() || { master: '📋', researcher: '🔎', builder: '🛠️', reviewer: '✅', reporter: '📝', helper: '🤝' }[botKind(id, role)]
}
/** Soft background behind each face. Same lightness and chroma for every kind; only the hue changes. */
export function botTint(kind: BotKind): string {
  return { master: 'oklch(0.92 0.05 65)', researcher: 'oklch(0.94 0.06 95)', builder: 'oklch(0.92 0.05 25)', reviewer: 'oklch(0.92 0.05 240)', reporter: 'oklch(0.93 0.05 330)', helper: 'oklch(0.93 0.05 150)' }[kind]
}

export function botKind(id: string, role?: string): BotKind {
  const key = (role || id).toLowerCase()
  if (['master', 'planner'].includes(key)) return 'master'
  if (key === 'researcher') return 'researcher'
  if (['reviewer', 'critic'].includes(key)) return 'reviewer'
  if (['builder', 'writer', 'maker'].includes(key)) return 'builder'
  if (key === 'reporter') return 'reporter'
  return 'helper'
}
export function botActivity(tasks: Task[], runStatus: string, id: string, role?: string, enabled = true): BotVisualState {
  if (!enabled) return 'disabled'
  // A terminal/stopped run must not continue animating stale running tasks.
  if (['cancelled', 'interrupted', 'failed'].includes(runStatus)) return 'stopped'
  if (tasks.some(t => t.status === 'approval_required')) return 'approval'
  if (tasks.some(t => ['blocked', 'failed', 'partial'].includes(t.status))) return 'blocked'
  if (tasks.length > 0 && tasks.every(t => t.status === 'accepted')) return 'done'
  if (['completed', 'partial'].includes(runStatus)) return tasks.length ? 'stopped' : 'idle'
  if (runStatus === 'approval_required') return 'waiting'
  if (runStatus === 'blocked') return tasks.length ? 'blocked' : 'idle'
  if (runStatus === 'planning' && botKind(id, role) === 'master') return 'thinking'
  if (runStatus === 'running' && tasks.some(t => t.status === 'running')) {
    switch (botKind(id, role)) {
      case 'master': return 'thinking'
      case 'researcher': return 'researching'
      case 'reviewer': return 'reviewing'
      default: return 'building'
    }
  }
  if (tasks.some(t => ['queued', 'ready', 'waiting', 'review_pending'].includes(t.status))) return 'waiting'
  return 'idle'
}
const LABELS: Record<BotVisualState, [string, string]> = {
  idle: ['出番待ち', 'On standby'], waiting: ['待機中', 'Waiting'], thinking: ['計画中', 'Planning'],
  researching: ['調査中', 'Researching'], building: ['作業中', 'Working'], reviewing: ['確認中', 'Reviewing'],
  done: ['担当分は完了', 'Assigned work done'], blocked: ['要確認', 'Needs attention'],
  approval: ['承認待ち', 'Awaiting approval'], stopped: ['停止中', 'Stopped'], disabled: ['お休み中', 'Disabled'],
}
export function botStateLabel(state: BotVisualState, lang: 'ja' | 'en' = 'ja'): string {
  return LABELS[state][lang === 'en' ? 1 : 0]
}

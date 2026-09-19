/** User-facing progress is a projection, not a new runtime status or a quality claim. */
export type JourneyPanel = 'request' | 'team' | 'results'
export type UiLanguage = 'ja' | 'en'
const finished = new Set(['completed', 'partial', 'failed', 'cancelled', 'interrupted', 'blocked'])
export function isSettled(status: string): boolean { return finished.has(status) }
export function defaultPanel(status: string, deliverables: number): JourneyPanel {
  return isSettled(status) && deliverables > 0 ? 'results' : 'team'
}
export function requestedPanel(search: string): JourneyPanel | null {
  const view = new URLSearchParams(search).get('view')
  return view === 'request' || view === 'team' || view === 'results' ? view : null
}
export function resultFiles<T extends { artifact_id: string }>(files: T[]): T[] {
  return files.filter(f => f.artifact_id !== 'final-report.md')
}
const statusCopy: Record<string, [string, string]> = {
  created: ['お願いを受け取りました', 'Request received'], queued: ['順番を待っています', 'Waiting to begin'],
  planning: ['進め方を考えています', 'Planning the work'], running: ['チームが進めています', 'Your team is working'],
  approval_required: ['あなたの確認が必要です', 'Your approval is needed'], completed: ['できたものを見てみよう', 'Your results are ready to view'],
  partial: ['できた分があります。まだ未完了です', 'Some work is ready. The request is not complete.'],
  failed: ['作業が止まりました', 'The work could not be completed'], cancelled: ['作業を停止しました', 'The work was stopped'],
  interrupted: ['作業が中断しています', 'The work was interrupted'], blocked: ['進めるための確認が必要です', 'Something needs attention'],
}
export function statusLabel(status: string, lang: UiLanguage): string {
  return (statusCopy[status] || ['状態を確認しています', 'Checking status'])[lang === 'en' ? 1 : 0]
}
export function roleLabel(role: string, lang: UiLanguage): string {
  const roles: Record<string, [string, string]> = { master: ['まとめ役', 'Coordinator'], researcher: ['調べる係', 'Researcher'], builder: ['つくる係', 'Maker'], reviewer: ['確かめる係', 'Reviewer'], reporter: ['伝える係', 'Reporter'], specialist: ['専用の仲間', 'Specialist'] }
  return (roles[role] || ['あなたの仲間', 'Your teammate'])[lang === 'en' ? 1 : 0]
}
export function stateTone(status: string): 'good' | 'attention' | 'working' {
  if (status === 'completed') return 'good'
  return isSettled(status) || status === 'approval_required' ? 'attention' : 'working'
}
/** Teammates appear in hand-off order (plan → research → make → check → report), not config order. */
const ROLE_ORDER = ['master', 'researcher', 'builder', 'reviewer', 'reporter']
export function teamOrder<T extends { role?: string }>(agents: [string, T][]): [string, T][] {
  const rank = (role?: string) => { const i = ROLE_ORDER.indexOf(role || ''); return i < 0 ? ROLE_ORDER.length : i }
  return agents.map((entry, i) => ({ entry, i })).sort((a, b) => rank(a.entry[1].role) - rank(b.entry[1].role) || a.i - b.i).map(x => x.entry)
}
/** Runtime reasons are written for the work record. Translate the recurring ones; unknown text passes through unchanged. */
const REASONS: [RegExp, string, string][] = [
  [/required independent review was not submitted/g, '確かめる係の確認がまだ出ていません', 'the reviewer has not submitted a check yet'],
  [/agent ended its turn repeatedly without (?:finish_task|using a tool)/g, '担当が「終わりました」の合図を出さないまま止まりました', 'the teammate stopped without reporting that the work was finished'],
  [/review left criteria unverified/g, '確認できていない条件が残っています', 'some acceptance criteria are still unverified'],
  [/wall-clock limit reached/g, '時間の上限に達しました', 'the time limit was reached'],
  [/\bpartial\b/g, '途中まで', 'partly done'], [/\bcancelled\b/g, '取りやめ', 'cancelled'], [/\bqueued\b/g, '順番待ち', 'waiting its turn'],
]
export function friendlyReason(text: string, lang: UiLanguage): string {
  return REASONS.reduce((out, [pattern, ja, en]) => out.replace(pattern, lang === 'en' ? en : ja), text)
}

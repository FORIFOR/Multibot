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
/** Check outcomes in everyday words. Unknown values are shown as "not checked", never as a pass. */
export function outcomeLabel(status: unknown, lang: UiLanguage): string {
  const copy: Record<string, [string, string]> = { pass: ['通過', 'Passed'], fail: ['要修正', 'Needs fixing'], unverified: ['未確認', 'Unverified'], blocked: ['確認できず', 'Could not check'] }
  return (copy[String(status)] || ['未確認', 'Unverified'])[lang === 'en' ? 1 : 0]
}
/** Setup problems in everyday words, keyed by the backend's stable codes. Unknown codes keep the original message. */
const PROBLEMS: Record<string, [string, string]> = {
  capability_check: ['AIへの接続が、まだ確かめられていません。マイチームの「接続」で「疎通確認」を押してください。', 'The model connection has not been checked yet. Open My team → Connection and run the connection check.'],
  no_master: ['まとめ役がお休みになっています。マイチームで、まとめ役を参加中にしてください。', 'The coordinator is switched off. Turn it on in My team.'],
  unknown_connection: ['仲間の接続先が見つかりません。マイチームで接続を選び直してください。', 'A teammate points to a connection that does not exist. Choose one in My team.'],
  placeholder_model: ['使うAIのモデル名が、まだ決まっていません。マイチームで入力してください。', 'A model name has not been set yet. Enter one in My team.'],
  driver_unsupported: ['この種類の接続には、まだ対応していません。別の接続を選んでください。', 'This kind of connection is not supported yet. Choose another.'],
  budget: ['1回のお願いに使う予算の上限が0になっています。マイチームの詳細設定で直してください。', 'The budget limit per request is zero. Fix it in My team → advanced settings.'],
  single_agent_shape: ['一人で進める設定では、つくる係を1人だけ参加中にしてください。', 'Single-agent mode needs exactly one maker switched on.'],
  fake_not_injected: ['テスト用の接続が選ばれています。実際のAIの接続を選んでください。', 'A test-only connection is selected. Choose a real model connection.'],
}
export function friendlyProblem(problem: { code: string; message: string }, lang: UiLanguage): string {
  const copy = PROBLEMS[problem.code]
  return copy ? copy[lang === 'en' ? 1 : 0] : problem.message
}
/** The coordinator's work is the plan, which is not a task. After the run has settled, a coordinator with a plan has
 *  done its part. While work is under way it may still replan, so it stays "on standby" rather than claiming completion. */
export function coordinatorPlanned(role: string | undefined, taskCount: number, hasPlan: boolean, state: string, runStatus: string): boolean {
  return role === 'master' && taskCount === 0 && hasPlan && state === 'idle' && isSettled(runStatus)
}
/** Models refer to work by internal marks ("t2", "brief.md r1"). On everyday screens show whose work it is and which
 *  version, in words. Only known task ids are rewritten; anything else is left exactly as written. */
export function friendlyWorkText(text: string, owners: Record<string, string>, lang: UiLanguage): string {
  const en = lang === 'en'
  return text
    .replace(/(^|[^\w.`/-])(t\d+)(?![\w.-])/g, (whole, lead: string, id: string) => owners[id] ? `${lead}${en ? `${owners[id]}'s task` : `${owners[id]}の作業`}` : whole)
    .replace(/([\w\u3040-\u30ff\u4e00-\u9fff.-]+\.[a-z0-9]{1,8})\s+r(\d+)(?![\w.-])/gi, (_whole, name: string, n: string) => en ? `${name} (version ${n})` : `${name}（第${n}版）`)
}

/** Personal names are separate from capability labels and remain user editable. */
export function botName(role: string, lang: UiLanguage = 'ja'): string {
  const names: Record<string, [string,string]> = {master:['レン','Ren'],researcher:['ミオ','Mio'],builder:['カイ','Kai'],reviewer:['スイ','Sui'],reporter:['ナギ','Nagi']}
  return names[role]?.[lang==='en'?1:0] || role
}

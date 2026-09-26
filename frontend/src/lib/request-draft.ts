/** Tab-scoped draft, never sent until submit; browser storage may be unavailable. */
export interface RequestDraft { goal: string; text: string; urls: string; files: { name: string; content: string }[]; budget: string; outputPath?: string; minChars?: string; maxChars?: string; excludedPhrases?: string; documentWorkflow?: boolean; adaptiveTeam?: boolean; selectedAgentIds?: string[] }
const key = 'agentteam.requestDraft'
const empty = (): RequestDraft => ({ goal: '', text: '', urls: '', files: [], budget: '' })
let hydrated = false
let memory: RequestDraft = empty()

/** Old or corrupted optional settings must not turn .trim() / .map() into a UI crash. */
function parseDraft(value: unknown): RequestDraft | undefined {
  if (!value || typeof value !== 'object') return undefined
  const v = value as Record<string, unknown>
  if (!['goal', 'text', 'urls', 'budget'].every(k => typeof v[k] === 'string') || !Array.isArray(v.files)) return undefined
  const files: RequestDraft['files'] = []
  for (const file of v.files) {
    if (!file || typeof file !== 'object' || typeof file.name !== 'string' || typeof file.content !== 'string') return undefined
    files.push({ name: file.name, content: file.content })
  }
  const draft: RequestDraft = { goal: v.goal as string, text: v.text as string, urls: v.urls as string, budget: v.budget as string, files }
  for (const field of ['outputPath', 'minChars', 'maxChars', 'excludedPhrases'] as const) {
    if (typeof v[field] === 'string') draft[field] = v[field]
  }
  for (const field of ['documentWorkflow', 'adaptiveTeam'] as const) {
    if (typeof v[field] === 'boolean') draft[field] = v[field]
  }
  if (Array.isArray(v.selectedAgentIds) && v.selectedAgentIds.every(id => typeof id === 'string')) {
    draft.selectedAgentIds = [...v.selectedAgentIds]
  }
  return draft
}

function copyDraft(value: RequestDraft): RequestDraft {
  return { ...value, files: value.files.map(file => ({ ...file })),
    ...(value.selectedAgentIds ? { selectedAgentIds: [...value.selectedAgentIds] } : {}) }
}

export function readRequestDraft(): RequestDraft {
  if (!hydrated) {
    hydrated = true
    try { memory = parseDraft(JSON.parse(sessionStorage.getItem(key) || 'null')) ?? memory }
    catch { /* Keep the in-memory draft when storage is unavailable. */ }
  }
  return copyDraft(memory)
}
export function saveRequestDraft(value: RequestDraft): boolean {
  const next = parseDraft(value)
  if (!next) return false
  memory = next
  hydrated = true
  try { sessionStorage.setItem(key, JSON.stringify(next)); return true }
  catch {
    // Do not restore an older saved request after a quota failure. The caller shows
    // that this draft is memory-only; if storage is entirely blocked, removal may fail too.
    try { sessionStorage.removeItem(key) } catch { /* No persistent-storage guarantee. */ }
    return false
  }
}
export function clearRequestDraft(): void {
  hydrated = true
  memory = empty()
  try { sessionStorage.removeItem(key) } catch { /* Memory has still been cleared. */ }
}

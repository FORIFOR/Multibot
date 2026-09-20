/** Tab-scoped draft, never sent until submit; browser storage may be unavailable. */
export interface RequestDraft { goal: string; text: string; urls: string; files: { name: string; content: string }[]; budget: string; outputPath?: string; minChars?: string; maxChars?: string; excludedPhrases?: string; documentWorkflow?: boolean; adaptiveTeam?: boolean; selectedAgentIds?: string[] }
const key = 'agentteam.requestDraft'
let hydrated = false
let memory: RequestDraft = { goal: '', text: '', urls: '', files: [], budget: '' }
export function readRequestDraft(): RequestDraft {
  if (hydrated) return memory
  hydrated = true
  try {
    const value = JSON.parse(sessionStorage.getItem(key) || 'null')
    if (value && ['goal','text','urls','budget'].every(k => typeof value[k] === 'string') && Array.isArray(value.files) && value.files.every((f: any) => typeof f.name === 'string' && typeof f.content === 'string')) memory = value
  } catch { /* Keep the in-memory draft when storage is unavailable. */ }
  return memory
}
export function saveRequestDraft(value: RequestDraft): boolean {
  memory = value
  hydrated = true
  try { sessionStorage.setItem(key, JSON.stringify(value)); return true } catch { return false }
}
export function clearRequestDraft(): void {
  hydrated = true
  memory = { goal: '', text: '', urls: '', files: [], budget: '' }
  try { sessionStorage.removeItem(key) } catch { /* Memory has still been cleared. */ }
}

/** Browser data belongs to the authenticated principal, never to the next person using this browser. */
export interface BrowserPrincipal { subject: string; organization: string | null; role: string; source?: string }
const TAB_OWNER = 'agentteam.tabOwner'
const BROWSER_OWNER = 'agentteam.browserOwner'
export const SESSION_CHANGE_KEY = 'agentteam.sessionChange'
export const SESSION_TAB_ID = crypto.randomUUID()
const PRIVATE_KEYS = new Set(['agentteam.requestDraft', 'agentteam.draftGoal', 'agentteam.welcomed', 'work-list-search', 'agentteam.pendingCommands'])
const resetters = new Set<() => void>()
let active = false
let generation = 0
let boundSubject: string | null = null
let changeSequence = 0

export function onBrowserSessionReset(reset: () => void): void { resetters.add(reset) }
export function browserSessionGeneration(): number { return generation }
export function browserSessionActive(): boolean { return active }
export function browserSessionSubject(): string | null { return active ? boundSubject : null }
export function suspendBrowserSession(): void { active = false; boundSubject = null; generation++ }
export function browserPrincipalKey(identity: BrowserPrincipal, secured: boolean): string {
  return JSON.stringify([secured, identity.organization, identity.source || (secured ? 'key' : 'local'), identity.subject, identity.role])
}

function clearPrivateStorage(storage: Storage): void {
  for (let i = storage.length - 1; i >= 0; i--) {
    const key = storage.key(i)
    if (key && (PRIVATE_KEYS.has(key) || key.startsWith('artifact-draft:'))) storage.removeItem(key)
  }
}

/** Call before unmounting an old workspace, so late effects cannot save its draft again. */
export function clearBrowserSession(): void {
  active = false
  boundSubject = null
  generation++
  try { clearPrivateStorage(sessionStorage); sessionStorage.removeItem(TAB_OWNER) } catch { /* Storage may be disabled. */ }
  try { clearPrivateStorage(localStorage); localStorage.removeItem(BROWSER_OWNER) } catch { /* Memory must still be cleared. */ }
  for (const reset of resetters) reset()
}

/** Preserve reloads for the same principal; discard legacy/unowned data and any other principal's data. */
export function bindBrowserSession(identity: BrowserPrincipal, secured: boolean): boolean {
  const owner = browserPrincipalKey(identity, secured)
  let tabOwner: string | null = null, browserOwner: string | null = null
  try { tabOwner = sessionStorage.getItem(TAB_OWNER) } catch { /* ignore */ }
  try { browserOwner = localStorage.getItem(BROWSER_OWNER) } catch { /* ignore */ }
  const changed = Boolean((tabOwner && tabOwner !== owner) || (browserOwner && browserOwner !== owner))
  if ((!tabOwner && !browserOwner) || changed) clearBrowserSession()
  try { sessionStorage.setItem(TAB_OWNER, owner) } catch { /* No persistent draft available. */ }
  try { localStorage.setItem(BROWSER_OWNER, owner) } catch { /* Cross-tab channel still works when available. */ }
  active = true
  boundSubject = secured ? identity.subject : null
  return changed
}

/** No identity, credential, or request content is written into the cross-tab notification. */
export function broadcastSessionChange(pending = false): void {
  const message = { sender: SESSION_TAB_ID, pending, sequence: ++changeSequence, nonce: crypto.randomUUID() }
  try { localStorage.setItem(SESSION_CHANGE_KEY, JSON.stringify(message)) } catch { /* Fall back to BroadcastChannel. */ }
  try { const channel = new BroadcastChannel(SESSION_CHANGE_KEY); channel.postMessage(message); channel.close() } catch { /* Focus revalidation remains available. */ }
}

/** Even if the server cannot be reached, the current browser must stop displaying private work. */
export async function signOut(): Promise<void> {
  const subject = browserSessionSubject()
  clearBrowserSession()
  broadcastSessionChange(true)
  window.dispatchEvent(new Event('agentteam:signout'))
  try {
    const response = await fetch('/api/auth/logout', { method: 'POST', headers: subject ? { 'X-AgentTeam-Subject': subject } : {}, signal: AbortSignal.timeout(15000) })
    if (!response.ok && response.status !== 401) throw new Error('logout failed')
    const result = response.ok ? await response.json() : {}
    broadcastSessionChange()
    window.location.assign(result.redirect || '/')
  } catch {
    // Keep the login screen visible; do not reload an unrevoked cookie into the old workspace.
    broadcastSessionChange()
    window.dispatchEvent(new Event('agentteam:signout-failed'))
  }
}

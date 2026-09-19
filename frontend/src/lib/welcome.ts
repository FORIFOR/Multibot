/** First-visit introduction state. Browser storage can be unavailable (private mode); every access is guarded. */
const SEEN = 'agentteam.welcomed', DRAFT = 'agentteam.draftGoal'
export function welcomed(): boolean { try { return localStorage.getItem(SEEN) === '1' } catch { return true } }
export function markWelcomed(): void { try { localStorage.setItem(SEEN, '1') } catch { /* ignore */ } }
export function setDraftGoal(goal: string): void { try { sessionStorage.setItem(DRAFT, goal.slice(0, 2000)) } catch { /* ignore */ } }
export function takeDraftGoal(): string { try { const v = sessionStorage.getItem(DRAFT) || ''; sessionStorage.removeItem(DRAFT); return v } catch { return '' } }
export const WELCOME_STEPS = 3
export function clampStep(n: number): number { return Number.isFinite(n) ? Math.min(WELCOME_STEPS - 1, Math.max(0, Math.trunc(n))) : 0 }

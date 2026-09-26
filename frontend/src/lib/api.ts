export type RunStatus = 'created' | 'queued' | 'planning' | 'running' | 'approval_required' | 'completed' | 'partial' | 'failed' | 'cancelled' | 'interrupted' | 'blocked'

export interface Usage { model_calls: number; tool_calls: number; input_tokens: number; output_tokens: number; cache_read_tokens: number; cache_write_tokens: number; cost_usd: number; reserved_usd: number; wall_seconds: number }
export interface ArtifactRef { artifact_id: string; revision: number; sha256: string }
export interface Acceptance { id: string; description: string; check_kind: string }
export interface TaskSpec { id: string; owner: string; objective: string; depends_on: string[]; output_paths: string[]; acceptance: Acceptance[]; write_scope: string }
export interface ReviewResult { acceptance_id: string; status: 'pass' | 'fail' | 'unverified' | 'blocked'; evidence: string; note: string }
export interface Review { target_task_id: string; target_artifacts: ArtifactRef[]; results: ReviewResult[]; summary: string }
export interface TaskState { run_id: string; spec: TaskSpec; status: string; attempt: number; revision_round: number; result: { summary: string; verified: string[]; unverified: string[]; next_steps: string[]; published: ArtifactRef[] } | null; blocked_reason: string | null; review: Review | null; updated_at: string }
export interface Artifact { run_id: string; artifact_id: string; revision: number; sha256: string; media_type: string; size: number; logical_path: string; task_id: string | null; agent_id: string; created_at: string; event_id: string | null; sources: string[] }
export interface Approval { approval_id: string; run_id: string; task_id: string | null; agent_id: string; action: string; payload: Record<string, unknown>; payload_hash: string; nonce: string; status: string; created_at: string; expires_at: string; resolution: Record<string, unknown> | null }
export interface Event { event_id: string; run_id: string; seq: number; recorded_at: string; actor_id: string; actor_kind: string; task_id: string | null; causation_id: string | null; type: string; payload: Record<string, any> }
export interface TeamPlan { goal: string; assumptions: string[]; agents: string[]; tasks: TaskSpec[] }
export interface Run {
  run_id: string; status: RunStatus; goal: string; inputs: { text: string; urls: string[]; files: { name: string; content: string }[]; workflow?: 'team' | 'document'; team_selection?: 'fixed' | 'adaptive'; selected_agent_ids?: string[]; delivery_requirements?: { logical_path: string; input_format: string; json_schema: Record<string, unknown> }[] }
  created_at: string; started_at: string | null; finished_at: string | null; usage: Usage; plan: TeamPlan | null
  config_snapshot: { agents?: Record<string, EffectiveAgent>; provider_kind?: string; team_recommendation?: {reason:string;members:{name:string;specialty:string;reason:string;personality:string}[]} } | null
  parent_run_id: string | null; fork_from_seq: number | null; final_report: any; blocked_reason: string | null; provider_kind: string
}
export interface RunDetail extends Run { latest_instruction?: Event | null; access?: { can_write: boolean; can_override: boolean; can_instruct?: boolean }; tasks: TaskState[]; artifacts: Artifact[]; approvals: Approval[]; artifact_selection?: Record<string, ArtifactSelection>; last_seq: number; live: boolean }
export interface ArtifactSelection { revision: number; seq: number; event_id: string; actor_id: string; note: string }
export interface ArtifactDiff { supported: boolean; from_revision: number; revision: number; artifact_id?: string; logical_path?: string; diff?: string; reason?: string }
export interface EffectiveAgent { agent_id: string; role: string; enabled: boolean; connection_id: string; driver: string; base_url: string; model: string; prompt_mode: string; system_prompt: string; system_prompt_sha256: string; skills: { name: string; description: string; sha256: string }[]; tools: string[]; effort: string | null; api_key_ref: string | null; display_name: string | null; emoji: string | null; speech_style?: string | null; specialty?: string | null; custom: boolean }
export interface AgentSpec { id: string; role: string; enabled: boolean; connection_id: string; model: string; system_prompt_file: string; prompt_mode: 'auto_seed' | 'user_locked'; skill_ids: string[]; tools: string[]; system_prompt_override: string | null; effort: string | null; display_name: string | null; emoji: string | null; speech_style?: string | null; specialty?: string | null; custom: boolean }
export interface Connection { id: string; driver: string; base_url: string; api_key_ref: string | null; capability_check: 'not_run' | 'passed' | 'failed'; capability_detail: any; refusal_fallback: boolean; ollama_thinking?: boolean | null; ollama_temperature?: number | null; ollama_top_p?: number | null }
export interface Problem { code: string; message: string; agent_id?: string; connection_id?: string; fix?: string }
export interface Config {
  execution_summary?: { driver: string; model: string; destination: string; tools: string[] }[]
  revision: number; profile_name: string; defaults: { team_mode?: 'team' | 'single'; connection_id: string; model: string; language: string; timezone: string }
  connections: Connection[]; limits: Record<string, number>; policy: Record<string, string>; agents: AgentSpec[]
  pricing: Record<string, { input_per_mtok: number; output_per_mtok: number }>; problems: Problem[]
  skills: { name: string; description: string; sha256: string }[]; effective_agents: Record<string, EffectiveAgent>
}
export interface ChatMessage { seq: number; event_id: string; recorded_at: string; from: string; to: string; task_id: string; purpose: string; text: string; artifact_refs: ArtifactRef[]; reply_to: string | null; causation_id: string | null }
export interface TimelineItem { seq: number; event_id: string; recorded_at: string; actor_id: string; actor_kind: string; task_id: string | null; causation_id: string | null; type: string; title: string; detail: string }
export interface InstructionReceipt { instruction_id: string; state: 'received'; seq: number; event: Event }

export class ApiError extends Error {
  status: number
  body: any
  constructor(status: number, body: any) {
    super(typeof body === 'string' ? body : body?.detail?.message || body?.detail || JSON.stringify(body))
    this.status = status
    this.body = body
  }
}

const pendingCommands = new Map<string, { input: string; key: string }>()

async function req<T>(method: string, url: string, body?: unknown, idempotent = false): Promise<T> {
  const input = body ? JSON.stringify(body) : ''
  const command = `${method} ${url}`
  if (idempotent && pendingCommands.get(command)?.input !== input) {
    pendingCommands.set(command, { input, key: crypto.randomUUID() })
  }
  const headers: Record<string, string> = body ? { 'content-type': 'application/json' } : {}
  if (idempotent) headers['Idempotency-Key'] = pendingCommands.get(command)!.key
  const send = () => fetch(url, { method, headers, body: input || undefined, ...(idempotent ? { signal: AbortSignal.timeout(30000) } : {}) })
  // A lost response is not proof of failure. Keep the key for an explicit retry;
  // never repeat a mutation just because its response did not arrive.
  const r = await send()
  const text = await r.text()
  let data: any = text
  try { data = text ? JSON.parse(text) : null } catch { /* keep text */ }
  if (r.status === 401) window.dispatchEvent(new Event('agentteam:unauthorized'))
  if (idempotent && r.status < 500) pendingCommands.delete(command)
  if (!r.ok) throw new ApiError(r.status, data)
  return data as T
}

export const api = {
  config: () => req<Config>('GET', '/api/config'),
  runs: () => req<Run[]>('GET', '/api/runs'),
  run: (id: string) => req<RunDetail>('GET', `/api/runs/${id}`),
  events: (id: string, after = 0) => req<Event[]>('GET', `/api/runs/${id}/events?after_seq=${after}`),
  chat: (id: string) => req<ChatMessage[]>('GET', `/api/runs/${id}/chat`),
  timeline: (id: string, tools = true) => req<TimelineItem[]>('GET', `/api/runs/${id}/timeline?tools=${tools}`),
  instruction: (id: string, body: { text: string; kind: 'change' | 'question' | 'edit' | 'control'; expected_seq?: number }) =>
    req<InstructionReceipt>('POST', `/api/runs/${id}/instructions`, body),
  createRun: (body: { goal: string; inputs: { text: string; urls: string[]; files: { name: string; content: string }[]; workflow?: 'team' | 'document'; team_selection?: 'fixed' | 'adaptive'; selected_agent_ids?: string[]; delivery_requirements?: { logical_path: string; input_format: string; json_schema: Record<string, unknown> }[] }; budget_usd?: number | null }) => req<Run>('POST', '/api/runs', body, true),
  cancel: (id: string) => req<{ cancel_requested: boolean }>('POST', `/api/runs/${id}/cancel`),
  resume: (id: string) => req<Run>('POST', `/api/runs/${id}/resume`, undefined, true),
  fork: (id: string, overrides: Record<string, unknown>) => req<Run>('POST', `/api/runs/${id}/fork`, { overrides, start: true }, true),
  health: () => req<{ ok: boolean; version: string; config_revision: number; live_runs: string[] }>('GET', '/api/health'),
  approvals: (status?: string) => req<Approval[]>('GET', `/api/approvals${status ? `?status=${status}` : ''}`),
  resolveApproval: (id: string, body: { decision: string; note?: string; expected_hash?: string; nonce?: string }) => req<Approval>('POST', `/api/approvals/${id}/resolve`, body),
  artifact: (runId: string, artifactId: string, rev: number) => req<Artifact & { text?: string; checks: Event[]; reviews: Event[] }>('GET', `/api/artifacts/${runId}/${artifactId}/versions/${rev}`),
  artifactDiff: (runId: string, artifactId: string, from: number, to: number) =>
    req<ArtifactDiff>('GET', `/api/artifacts/${runId}/${artifactId}/versions/${to}/diff?from_revision=${from}`),
  adoptArtifact: (runId: string, artifactId: string, body: { revision: number; expected_selected_revision?: number; note?: string }) =>
    req<{ artifact_id: string; revision: number; seq: number; event: Event }>('POST', `/api/artifacts/${runId}/${artifactId}/adopt`, body),
  artifactRawUrl: (runId: string, artifactId: string, rev: number) => `/api/artifacts/${encodeURIComponent(runId)}/${encodeURIComponent(artifactId)}/versions/${rev}/raw`,
  patchAgent: (id: string, body: Record<string, unknown>) => req<{ revision: number }>('PATCH', `/api/agents/${id}`, body),
  createAgent: (body: Record<string, unknown>) => req<{ revision: number; agent: AgentSpec }>('POST', '/api/agents', body),
  putConnection: (id: string, body: Record<string, unknown>) => req<{ revision: number }>('PUT', `/api/connections/${id}`, body),
  probe: (id: string, model?: string) => req<{ revision: number; result: any; capability_check: string }>('POST', `/api/connections/${id}/probe${model ? `?model=${encodeURIComponent(model)}` : ''}`),
  putLimits: (body: Record<string, unknown>) => req<{ revision: number }>('PUT', '/api/limits', body),
  defaultPrompt: async (id: string) => (await fetch(`/api/agents/${id}/prompt/default`)).text(),
}

export function fmtTime(iso: string | null | undefined, tz?: string): string {
  if (!iso) return '—'
  try {
    return new Intl.DateTimeFormat('ja-JP', { timeZone: tz, hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }).format(new Date(iso))
  } catch { return iso }
}
export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  try { return new Intl.DateTimeFormat('ja-JP', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(iso)) } catch { return iso }
}
// Four decimals keep small model costs visible; trailing zeros beyond cents carry no information ($5.00, $0.037).
export const money = (n: number) => `$${n.toFixed(4).replace(/(\.\d\d\d*?)0+$/, '$1')}`
export const short = (s: string, n = 10) => s.slice(0, n)
export const TERMINAL: RunStatus[] = ['completed', 'partial', 'failed', 'cancelled']

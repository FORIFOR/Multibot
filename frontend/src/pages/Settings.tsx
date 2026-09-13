import { t } from '../lib/i18n'
import { useEffect, useState } from 'react'
import { api, ApiError, type AgentSpec, type Config, type Connection } from '../lib/api'

const DRIVERS = ['anthropic_messages', 'openai_compatible_chat', 'ollama']
const EFFORTS = ['', 'low', 'medium', 'high', 'xhigh', 'max']

export default function Settings() {
  const [cfg, setCfg] = useState<Config | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const load = () => api.config().then(setCfg).catch((e) => setErr(String(e)))
  useEffect(() => { load() }, [])
  const guard = async (fn: () => Promise<unknown>, ok: string) => {
    setErr(null); setNote(null)
    try { await fn(); setNote(ok); await load() } catch (e) {
      if (e instanceof ApiError && e.status === 409) { setErr(t('設定が別の場所で更新されました。再読み込みします。')); await load() } else setErr(String(e))
    }
  }
  if (!cfg) return <p className="muted">{err || t('読み込み中…')}</p>
  return (
    <div className="stack">
      <div className="row">
        <h1>{t("設定")}</h1>
        <span className="tag">revision {cfg.revision}</span>
        <span className="muted small">{t("変更は次の run から反映されます。進行中の run は開始時のスナップショットで動きます。")}</span>
      </div>
      {cfg.problems.length > 0 && <div className="banner warn">{cfg.problems.map((p) => <div key={p.code + (p.agent_id || p.connection_id || '')}>{p.message}</div>)}</div>}
      {cfg.problems.length === 0 && <div className="banner ok">{t("開始条件を満たしています。")}</div>}
      {err && <p className="err">{err}</p>}
      {note && <p className="small" style={{ color: 'var(--ok)' }}>{note}</p>}
      <div className="settings">
        <div className="stack">
          <h3>{t("接続（API キーは参照のみ保存: env:NAME / keychain:service/account / file:/path）")}</h3>
          {cfg.connections.map((c) => <ConnectionCard key={c.id} c={c} cfg={cfg} guard={guard} />)}
          <NewConnection cfg={cfg} guard={guard} />
          <h3>{t("既定と上限")}</h3>
          <LimitsCard cfg={cfg} guard={guard} />
        </div>
        <div className="stack">
          <h3>{t("Bot（共通設定を継承し、必要なものだけ上書き）")}</h3>
          {cfg.agents.map((a) => <AgentCard key={a.id} a={a} cfg={cfg} guard={guard} />)}
        </div>
      </div>
    </div>
  )
}

function ConnectionCard({ c, cfg, guard }: { c: Connection; cfg: Config; guard: (fn: () => Promise<unknown>, ok: string) => Promise<void> }) {
  const [driver, setDriver] = useState(c.driver)
  const [baseUrl, setBaseUrl] = useState(c.base_url)
  const [keyRef, setKeyRef] = useState(c.api_key_ref || '')
  const [fallback, setFallback] = useState(c.refusal_fallback)
  const [thinking, setThinking] = useState<boolean | null>(c.ollama_thinking ?? null)
  const [probeModel, setProbeModel] = useState(cfg.defaults.model)
  const [probing, setProbing] = useState(false)
  const dirty = driver !== c.driver || baseUrl !== c.base_url || (keyRef || null) !== c.api_key_ref || fallback !== c.refusal_fallback || thinking !== (c.ollama_thinking ?? null)
  const d = c.capability_detail
  return (
    <div className="card stack">
      <div className="row"><b className="mono">{c.id}</b><span className={'tag ' + (c.capability_check === 'passed' ? 'pass' : c.capability_check === 'failed' ? 'fail' : 'unverified')}>capability {c.capability_check}</span>{cfg.defaults.connection_id === c.id && <span className="tag">default</span>}</div>
      <div className="row">
        <select className="input" style={{ width: 220 }} value={driver} onChange={(e) => setDriver(e.target.value)}>{(DRIVERS.includes(driver) ? DRIVERS : [...DRIVERS, driver]).map((x) => <option key={x}>{x}</option>)}</select>
        <input className="input" style={{ flex: 1 }} value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="base URL" />
      </div>
      <div className="row">
        <input className="input" style={{ flex: 1 }} value={keyRef} onChange={(e) => setKeyRef(e.target.value)} placeholder={t("api_key_ref 例: env:ANTHROPIC_API_KEY")} />
        {driver === 'anthropic_messages' && <label className="lock" title={t("Anthropic のサーバ側 refusal fallback（別モデルへ自動ルーティング）。既定 OFF。")}><input type="checkbox" checked={fallback} onChange={(e) => setFallback(e.target.checked)} /> refusal fallback</label>}
        <button className="btn sm" disabled={!dirty} onClick={() => guard(() => api.putConnection(c.id, { expected_revision: cfg.revision, driver, base_url: baseUrl, api_key_ref: keyRef || null, refusal_fallback: fallback, ollama_thinking: driver === 'ollama' ? thinking : null }), t('接続を保存しました（要 再疎通確認）'))}>{t("保存")}</button>
      </div>
      {driver === 'ollama' && <label className="row small">{t('推論モード（Ollama）')}
        <select className="input" style={{ width: 180 }} value={thinking === null ? 'default' : String(thinking)} onChange={(e) => setThinking(e.target.value === 'default' ? null : e.target.value === 'true')}>
          <option value="default">{t('サーバーの既定')}</option><option value="false">{t('無効')}</option><option value="true">{t('有効')}</option>
        </select><span className="muted">{t('短い出力で回答が空になる場合は無効を試してください。')}</span>
      </label>}
      <div className="row">
        <input className="input" style={{ width: 240 }} value={probeModel} onChange={(e) => setProbeModel(e.target.value)} placeholder="probe model" />
        <button className="btn sm ghost" disabled={probing || dirty} onClick={async () => { setProbing(true); await guard(() => api.probe(c.id, probeModel), t('疎通確認を実行しました')); setProbing(false) }}>{probing ? '確認中…' : t('疎通確認（実 API 呼出・少額）')}</button>
        <span className="muted small">{t("tool calling と JSON schema 出力を実際に試します。")}</span>
      </div>
      {d && <div className="probe">{`requested ${d.model_requested} → reported ${d.model_reported ?? 'unknown'}\ntool_calling ${d.tool_calling}  json_schema ${d.json_schema}\n${d.error ? 'error: ' + d.error : 'ok'}${d.usage ? `\nusage in=${d.usage.input_tokens} out=${d.usage.output_tokens}` : ''}`}</div>}
    </div>
  )
}

function NewConnection({ cfg, guard }: { cfg: Config; guard: (fn: () => Promise<unknown>, ok: string) => Promise<void> }) {
  const [id, setId] = useState('')
  const [driver, setDriver] = useState('openai_compatible_chat')
  const [baseUrl, setBaseUrl] = useState('')
  const [keyRef, setKeyRef] = useState('')
  return (
    <details className="card flat">
      <summary className="muted small">{t("接続を追加（例: ローカル Ollama = driver ollama, http://localhost:11434/v1, キーなし）")}</summary>
      <div className="row" style={{ marginTop: 8 }}>
        <input className="input" style={{ width: 120 }} placeholder="id" value={id} onChange={(e) => setId(e.target.value)} />
        <select className="input" style={{ width: 200 }} value={driver} onChange={(e) => setDriver(e.target.value)}>{DRIVERS.map((x) => <option key={x}>{x}</option>)}</select>
        <input className="input" style={{ flex: 1 }} placeholder="base URL" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
        <input className="input" style={{ width: 200 }} placeholder="api_key_ref" value={keyRef} onChange={(e) => setKeyRef(e.target.value)} />
        <button className="btn sm" disabled={!id || !baseUrl} onClick={() => guard(() => api.putConnection(id, { expected_revision: cfg.revision, driver, base_url: baseUrl, api_key_ref: keyRef || null }), t('接続を追加しました'))}>{t("追加")}</button>
      </div>
    </details>
  )
}

function LimitsCard({ cfg, guard }: { cfg: Config; guard: (fn: () => Promise<unknown>, ok: string) => Promise<void> }) {
  const [limits, setLimits] = useState<Record<string, number>>(cfg.limits)
  const [model, setModel] = useState(cfg.defaults.model)
  const [conn, setConn] = useState(cfg.defaults.connection_id)
  const [pricing, setPricing] = useState(JSON.stringify(cfg.pricing, null, 1))
  useEffect(() => { setLimits(cfg.limits); setModel(cfg.defaults.model); setConn(cfg.defaults.connection_id); setPricing(JSON.stringify(cfg.pricing, null, 1)) }, [cfg])
  const keys = ['budget_usd', 'max_model_calls', 'max_tool_calls', 'timeout_seconds', 'max_active_workers', 'max_tasks', 'max_peer_messages_per_task', 'max_revision_rounds', 'max_output_tokens']
  return (
    <div className="card stack">
      <div className="row">
        <label className="small muted">{t("既定モデル")}</label><input className="input" style={{ width: 220 }} value={model} onChange={(e) => setModel(e.target.value)} />
        <label className="small muted">{t("既定接続")}</label>
        <select className="input" style={{ width: 160 }} value={conn} onChange={(e) => setConn(e.target.value)}>{cfg.connections.map((c) => <option key={c.id}>{c.id}</option>)}</select>
      </div>
      <div className="agentcard" style={{ border: 0, padding: 0 }}>
        <div className="grid">
          {keys.map((k) => <div key={k}><label>{k}</label><input className="input" type="number" step={k === 'budget_usd' ? '0.1' : '1'} value={limits[k] ?? ''} onChange={(e) => setLimits({ ...limits, [k]: Number(e.target.value) })} /></div>)}
        </div>
      </div>
      <details><summary className="muted small">{t("価格表（USD / 1M tokens）。価格不明のクラウドモデルは開始できません。")}</summary>
        <textarea className="input mono" style={{ minHeight: 120 }} value={pricing} onChange={(e) => setPricing(e.target.value)} /></details>
      <div><button className="btn sm" onClick={() => guard(() => api.putLimits({ expected_revision: cfg.revision, limits, defaults: { model, connection_id: conn }, pricing: JSON.parse(pricing || '{}') }), t('既定と上限を保存しました'))}>{t("保存")}</button></div>
    </div>
  )
}

function AgentCard({ a, cfg, guard }: { a: AgentSpec; cfg: Config; guard: (fn: () => Promise<unknown>, ok: string) => Promise<void> }) {
  const eff = cfg.effective_agents[a.id]
  const [prompt, setPrompt] = useState(eff?.system_prompt || '')
  const [open, setOpen] = useState(false)
  useEffect(() => { setPrompt(eff?.system_prompt || '') }, [eff?.system_prompt])
  const patch = (body: Record<string, unknown>, ok: string) => guard(() => api.patchAgent(a.id, { expected_revision: cfg.revision, ...body }), ok)
  const promptDirty = prompt !== (eff?.system_prompt || '')
  return (
    <div className="agentcard">
      <header>
        <span className="role">{a.id}</span><span className="tag">{a.role}</span>
        <label className="lock" style={{ marginLeft: 'auto' }} onClick={() => patch({ enabled: !a.enabled }, `${a.id} を${a.enabled ? '無効' : t('有効')}化しました`)}><span className={'switch' + (a.enabled ? ' on' : '')} /> {a.enabled ? 'enabled' : 'disabled'}</label>
      </header>
      <div className="grid">
        <div><label>connection</label>
          <select className="input" value={a.connection_id} onChange={(e) => patch({ connection_id: e.target.value }, t('接続を変更しました'))}>
            <option value="inherit">inherit ({cfg.defaults.connection_id})</option>{cfg.connections.map((c) => <option key={c.id} value={c.id}>{c.id}</option>)}</select></div>
        <div><label>model</label><input className="input" defaultValue={a.model} onBlur={(e) => { if (e.target.value !== a.model) patch({ model: e.target.value || 'inherit' }, t('モデルを変更しました')) }} placeholder={`inherit (${cfg.defaults.model})`} /></div>
        <div><label>effort</label>
          <select className="input" value={a.effort || ''} onChange={(e) => patch({ effort: e.target.value }, t('effort を変更しました'))}>{EFFORTS.map((x) => <option key={x} value={x}>{x || 'default'}</option>)}</select></div>
        <div><label>{t("実効")}</label><div className="mono small">{eff ? `${eff.model} @ ${eff.connection_id}/${eff.driver}` : '—'}</div></div>
      </div>
      <div className="row" style={{ marginTop: 8 }}>
        <span className="muted small">skills: {a.skill_ids.join(', ') || '—'}</span>
        <span className="muted small">tools: {a.tools.length}</span>
        <button className="btn sm ghost" style={{ marginLeft: 'auto' }} onClick={() => setOpen(!open)}>{open ? 'プロンプトを閉じる' : t('システムプロンプト')}</button>
      </div>
      {open && (
        <div className="stack" style={{ marginTop: 8 }}>
          <div className="row">
            <label className="lock" onClick={() => patch({ prompt_mode: a.prompt_mode === 'user_locked' ? 'auto_seed' : 'user_locked' }, t('ロック状態を変更しました'))}>
              <span className={'switch' + (a.prompt_mode === 'user_locked' ? ' on' : '')} /> 手動固定（Master は上書きしない）
            </label>
            <span className="mono muted small">sha256 {eff?.system_prompt_sha256.slice(0, 12)} · {a.system_prompt_override != null ? 'ユーザー編集版' : `ファイル ${a.system_prompt_file}`}</span>
          </div>
          <textarea className="input" value={prompt} onChange={(e) => setPrompt(e.target.value)} />
          <div className="row">
            <button className="btn sm" disabled={!promptDirty} onClick={() => patch({ system_prompt_override: prompt }, t('プロンプトを保存しました（新 revision）'))}>{t("保存")}</button>
            <button className="btn sm ghost" disabled={a.system_prompt_override == null} onClick={() => patch({ reset_prompt: true }, t('同梱プロンプトに戻しました'))}>{t("元に戻す")}</button>
            {promptDirty && <span className="muted small">差分 {prompt.length - (eff?.system_prompt.length || 0)} 文字</span>}
          </div>
        </div>
      )}
    </div>
  )
}

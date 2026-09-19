import { t, getLang } from '../lib/i18n'
import { useCallback, useEffect, useState } from 'react'
import { api, ApiError, type Config, type Connection } from '../lib/api'

import CustomBotCreator from '../components/CustomBotCreator'
import BotSettingsCard from '../components/BotSettingsCard'

const DRIVERS = ['anthropic_messages', 'openai_compatible_chat', 'ollama']


export default function Settings() {
  const [cfg, setCfg] = useState<Config | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const refresh = useCallback(async () => { const value = await api.config(); setCfg(value); return value }, [])
  const load = () => refresh().catch(e => setErr(String(e)))
  useEffect(() => { void refresh().catch(e => setErr(String(e))) }, [refresh])
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
        <h1>{getLang() === "en" ? "My team" : "マイチーム"}</h1>
        <span className="muted small">{getLang() === "en" ? "Changes apply to your next request. Work in progress keeps its original team." : "変更は次のお願いから反映します。進行中のお仕事のチームは変わりません。"}</span>
      </div>
      {cfg.problems.length > 0 && <div className="banner warn"><strong>{getLang() === "en" ? "Your team needs a little setup" : "チームの準備が必要です"}</strong><p>{getLang() === "en" ? "Open the connection settings below to prepare your first request." : "下の「チームの接続・予算」から準備できます。"}</p><details><summary>{getLang() === "en" ? "Setup details" : "設定の詳細"}</summary>{cfg.problems.map((p) => <p key={p.code + (p.agent_id || p.connection_id || '')}>{p.message}</p>)}</details></div>}
      {cfg.problems.length === 0 && <div className="banner ok">{t("開始条件を満たしています。")}</div>}
      {err && <p className="err">{err}</p>}
      {note && <p className="small" style={{ color: 'var(--ok)' }}>{note}</p>}
      <section className="bot-settings-section">
        <CustomBotCreator cfg={cfg} refresh={refresh} />
        <h2>{getLang() === 'en' ? 'Your team' : 'あなたのチーム'}</h2>
        <div className="bot-settings-grid">{cfg.agents.map(a => <BotSettingsCard key={a.id} a={a} cfg={cfg} refresh={refresh} />)}</div>
      </section>
      <details className="connection-settings"><summary>{getLang() === 'en' ? 'Team connection & budget (advanced)' : 'チームの接続・予算（詳細設定）'}</summary>
      <p className="muted small">{getLang() === "en" ? "Configuration revision" : "設定の更新番号"}: {cfg.revision}</p>
      <div className="settings">
        <div className="stack">
          <h3>{t("接続（API キーは参照のみ保存: env:NAME / keychain:service/account / file:/path）")}</h3>
          {cfg.connections.map((c) => <ConnectionCard key={c.id} c={c} cfg={cfg} guard={guard} />)}
          <NewConnection cfg={cfg} guard={guard} />
          <h3>{t("既定と上限")}</h3>
          <LimitsCard cfg={cfg} guard={guard} />
        </div>

      </div>
      </details>
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


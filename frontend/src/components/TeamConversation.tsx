import { botName } from '../lib/journey'
import {useEffect,useRef,useState, type ReactNode} from 'react'
import {api,fmtTime, type ArtifactRef,type ChatMessage, type Event, type RunDetail} from '../lib/api'
import {getLang} from '../lib/i18n'
import BotAvatar from './BotAvatar'
import ElapsedTime from './ElapsedTime'
import ConversationActivity from './ConversationActivity'

export default function TeamConversation({run,chat,events,connection,children,onOpenArtifact}:{run:RunDetail;chat:ChatMessage[];events:Event[];connection:string;children:ReactNode;onOpenArtifact?:(ref:ArtifactRef)=>void}) {
  const en=getLang()==='en', box=useRef<HTMLDivElement>(null)
  const [follow,setFollow]=useState(true),[seen,setSeen]=useState(0)
  const [query,setQuery]=useState(''),[agent,setAgent]=useState('')
  const filtered=chat.filter(m=>(!agent || m.from===agent || m.to===agent) && m.text.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()))
  const filtering=!!(query || agent)
  const participants=[...new Set(chat.flatMap(m=>[m.from,m.to]))]
  const last=chat.at(-1)?.seq || 0
  useEffect(()=>{if(follow){if(box.current) box.current.scrollTop=box.current.scrollHeight;setSeen(last)}},[last,follow])
  const name=(id:string)=>run.config_snapshot?.agents?.[id]?.display_name || botName(run.config_snapshot?.agents?.[id]?.role || id,getLang())
  const purposes:Record<string,string>=en?{request:'Request',question:'Question',answer:'Answer',handoff:'Handoff',finding:'Finding',decision:'Decision'}:{request:'依頼',question:'質問',answer:'回答',handoff:'引き継ぎ',finding:'発見・指摘',decision:'判断'}
  const activities:Record<string,string>=en?{'task.started':'Started work','model.called':'Model response received','input.read':'Read source material','artifact.published':'Saved an artifact','review.submitted':'Recorded a review','check.completed':'Ran a check'}:{'task.started':'作業を開始','model.called':'モデルの応答を受信','input.read':'元資料を参照','artifact.published':'成果物を保存','review.submitted':'確認結果を記録','check.completed':'検査を実行'}
  return <section className="team-conversation pane live-conversation" aria-label={en?'Team chat':'チームの会話'}>
    <header><div><h2>{en?'Team chat':'チームの会話'}</h2></div><div className="conversation-live-meta"><ElapsedTime run={run} events={events} /><span className={`stream-state is-${connection}`}>{connection==='live'?(en?'Live updates':'ライブ更新'):connection==='reconnecting'?(en?'Reconnecting · checking state':'再接続中・状態を照会'):connection==='ended'?(en?'Recorded conversation':'保存された会話'):(en?'Connecting':'接続中')}</span></div></header>
    <ConversationActivity run={run} events={events} connection={connection} />
    <div className="conversation-toolbar"><span>{chat.length} {en?'messages':'件の会話'}</span><button type="button" className="btn ghost" aria-pressed={follow} disabled={filtering} onClick={()=>setFollow(!follow)}>{follow?(en?'Following latest':'最新を自動追従'):(en?'Auto-follow paused':'自動追従を停止中')}</button></div>
    {chat.length>0 && <details className="conversation-filters"><summary>{en?'Find a message':'会話を探す'}{filtering && ` · ${filtered.length}${en?' matches':'件'}`}</summary><div>
      <input className="input" type="search" aria-label={en?'Search messages':'会話を検索'} placeholder={en?'Search messages…':'会話を検索…'} value={query} onChange={e=>{setQuery(e.target.value);setFollow(false)}} />
      <select className="input" aria-label={en?'Participant':'担当で絞り込み'} value={agent} onChange={e=>{setAgent(e.target.value);setFollow(false)}}><option value="">{en?'Everyone':'全員'}</option>{participants.map(id=><option value={id} key={id}>{name(id)}</option>)}</select>
      {filtering&&<button type="button" className="btn ghost" onClick={()=>{setQuery('');setAgent('')}}>{en?'Clear filters':'絞り込みを解除'}</button>}
    </div></details>}
    <div className="conversation-scroll" ref={box} role="log" aria-label={en?'Delivered team messages':'届いたチーム会話'} aria-live={follow?'polite':'off'} tabIndex={0} onScroll={()=>{const el=box.current;if(el && el.scrollHeight-el.scrollTop-el.clientHeight>64) setFollow(false)}}>
      {filtered.length?filtered.map(m=><article className="conversation-message" key={m.event_id} data-message-id={m.event_id}><BotAvatar id={m.from} emoji={run.config_snapshot?.agents?.[m.from]?.emoji} role={run.config_snapshot?.agents?.[m.from]?.role} name={name(m.from)} state="idle" size="micro"/><div className="message-body"><div className="message-meta"><strong>{name(m.from)}</strong><span>→ {name(m.to)}</span><span className="message-purpose">{purposes[m.purpose]||m.purpose}</span><time>{fmtTime(m.recorded_at)}</time></div>{m.text.length>1200?<details onToggle={e=>{if(e.currentTarget.open)setFollow(false)}}><summary>{en?'Open long message':'長いメッセージを開く'} ({m.text.length})</summary><p className="message-text">{m.text}</p></details>:<p className="message-text">{m.text}</p>}{m.artifact_refs?.length>0&&<p className="message-refs">{m.artifact_refs.map(r=><a key={`${r.artifact_id}@${r.revision}`} href={api.artifactRawUrl(run.run_id,r.artifact_id,r.revision)} onClick={e=>{if(onOpenArtifact&&!e.metaKey&&!e.ctrlKey&&!e.shiftKey&&!e.altKey){e.preventDefault();onOpenArtifact(r)}}}>{r.artifact_id} · {en?'version':'版'} {r.revision} ↗</a>)}</p>}</div></article>):<div className="conversation-empty">{filtering?(en?'No matching messages':'一致する発言はありません'):(en?'No messages yet':'まだ発言はありません')}</div>}
    </div>
    {!follow&&<button type="button" className="conversation-new btn signal" onClick={()=>{setQuery('');setAgent('');setFollow(true)}}>{chat.filter(m=>m.seq>seen).length>0?`${chat.filter(m=>m.seq>seen).length}${en?' new · ': '件の新着 · '}`:''}{en?'Jump to latest':'最新へ戻る'}</button>}
    <details className="conversation-activity"><summary>{en?'Activity log':'作業記録'}</summary>{events.filter(e=>activities[e.type]).slice(-3).map(e=><p key={e.event_id}><time>{fmtTime(e.recorded_at)}</time><span>{name(e.actor_id)} · {activities[e.type]}{e.payload.tool?` · ${e.payload.tool}`:''}{e.payload.result?.status?` · ${e.payload.result.status}`:''}</span></p>)}{!events.some(e=>activities[e.type])&&<p>{en?'No records yet.':'記録はまだありません。'}</p>}</details>
    <details className="conversation-direction" open><summary>{en?'Send a direction':'指示を送る'}</summary>{children}</details>
  </section>
}

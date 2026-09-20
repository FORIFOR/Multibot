import {useEffect,useRef,useState} from 'react'
import {api,type Artifact,type ArtifactDiff} from '../lib/api'
import {getLang} from '../lib/i18n'

/** A local editable copy. It never publishes or overwrites an agent's artifact. */
export default function ArtifactWorkbench({file,text,previous,onDirection}:{file:Artifact;text:string;previous?:number;onDirection:(text:string)=>void}) {
  const en=getLang()==='en', key=`artifact-draft:${file.run_id}:${file.artifact_id}:${file.revision}:${file.sha256}`
  const [editing,setEditing]=useState(false),[draft,setDraft]=useState(()=>{try{return localStorage.getItem(key)??text}catch{return text}})
  const [saved,setSaved]=useState(''),[diff,setDiff]=useState<ArtifactDiff|null>(null),[diffOpen,setDiffOpen]=useState(false),[error,setError]=useState('')
  const editor=useRef<HTMLTextAreaElement>(null)
  useEffect(()=>{if(!diffOpen || previous==null)return;let alive=true;setDiff(null);setError('');api.artifactDiff(file.run_id,file.artifact_id,previous,file.revision).then(d=>{if(alive)setDiff(d)}).catch(()=>{if(alive)setError(en?'Could not load changes. Close and reopen to retry.':'差分を取得できません。閉じて再度開くと再試行できます。')});return()=>{alive=false}},[diffOpen,previous,file.run_id,file.artifact_id,file.revision,en])
  const update=(value:string)=>{setDraft(value);try{localStorage.setItem(key,value);setSaved(en?'Draft saved in this browser':'このブラウザーに下書き保存済み')}catch{setSaved(en?'Not saved. Download a copy before leaving.':'下書きを保存できません。閉じる前にファイルを保存してください。')}}
  const download=()=>{const url=URL.createObjectURL(new Blob([draft],{type:'text/plain;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=file.logical_path.split('/').at(-1)||'draft.txt';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
  const direction=()=>{const el=editor.current;const excerpt=editing&&el&&el.selectionEnd>el.selectionStart?draft.slice(el.selectionStart,el.selectionEnd):'';onDirection(`${en?'Target':'対象'}: ${file.logical_path} · ${en?'version':'版'} ${file.revision}\nSHA256: ${file.sha256}\n${excerpt?`${en?'Selected text (editable copy)':'選択箇所（編集中のコピー）'}:\n${excerpt.slice(0,1800)}${excerpt.length>1800?'…':''}\n`:''}${en?'Requested change:':'修正内容：'}`)}
  return <div className="artifact-workbench">
    <div className="studio-tools"><button className="btn ghost" aria-expanded={editing} onClick={()=>setEditing(!editing)}>{editing?(en?'Close editor':'編集を閉じる'):(en?'Edit a copy':'コピーを編集')}</button><button className="btn ghost" onClick={direction}>{en?'Request a change':'この版の修正を頼む'}</button>{previous!=null&&<button className="btn ghost" aria-expanded={diffOpen} onClick={()=>setDiffOpen(!diffOpen)}>{en?'Changes from previous version':'前の版との差分'}</button>}</div>
    {editing&&<section className="studio-editor" aria-label={en?'Editable copy':'成果物の編集コピー'}><p>{en?'Local draft. Agent versions and checks stay unchanged. Select text to prepare a targeted instruction.':'手元の下書きです。チームの版・確認記録は変更しません。範囲を選ぶと、その箇所の修正を頼めます。'}</p><textarea ref={editor} aria-label={en?'Edit artifact copy':'成果物のコピーを編集'} value={draft} onChange={e=>update(e.target.value)} spellCheck={false}/><div className="studio-tools"><button className="btn signal" onClick={download}>{en?'Save a copy':'コピーをファイルに保存'}</button><button className="btn ghost" onClick={()=>update(text)} disabled={draft===text}>{en?'Restore this version':'この版の原文に戻す'}</button><span role="status">{saved}</span></div></section>}
    {diffOpen&&<section className="studio-diff" aria-label={en?'Version changes':'版の差分'}><h3>{en?'Version':'版'} {previous} → {file.revision}</h3>{error?<p role="alert">{error}</p>:!diff?<p role="status">{en?'Loading…':'読み込み中…'}</p>:diff.supported?<pre tabIndex={0}>{diff.diff|| (en?'No text changes':'本文に変更はありません')}</pre>:<p>{en?'Text comparison is not available for this file.':'この形式はテキスト比較できません。'}</p>}</section>}
  </div>
}

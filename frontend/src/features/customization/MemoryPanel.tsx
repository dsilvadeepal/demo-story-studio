import {useState} from 'react';
import type {MemoryItem} from './types';
type Props={items:MemoryItem[];usedIds:string[];busy:boolean;onConfirm:(item:MemoryItem)=>void;onIgnore:(id:string)=>void;onUpdate:(item:MemoryItem,text:string)=>void;onForget:(id:string)=>void};
function MemoryCard({item,used,...props}:Omit<Props,'items'|'usedIds'>&{item:MemoryItem;used:boolean}){
 const [wording,setWording]=useState(item.draft.text);
 const label:Record<string,string>={proposed:'Draft · review before saving',confirmed:'Not yet saved',saving:'Saving…',saved:'Saved',unknown:'Save unverified · check status before retrying',failed:'Save failed', 'deletion-pending':'Deletion pending · no longer used',deleted:'Deleted'};
 return <article className="memory-card"><strong>{item.draft.kind==='recipe'?'Recipe':'Preference'}</strong>{used&&<p className="approval-note">Used in this conversation</p>}<blockquote>{item.draft.text}</blockquote><p>{item.draft.scope.domain} · {item.draft.scope.audience} · {item.draft.scope.intent}</p>{item.draft.source_revision_id&&<small>Source revision: {item.draft.source_revision_id}</small>}<p role="status">{label[item.status]||item.status}</p>
 {['proposed','confirmed','unknown'].includes(item.status)&&<button disabled={props.busy} onClick={()=>props.onConfirm(item)}>{item.status==='unknown'?'Check save status':item.status==='confirmed'?'Retry save':'Confirm & save'}</button>}
 {used&&<button disabled={props.busy} onClick={()=>props.onIgnore(item.id)}>Ignore for this conversation</button>}
 {['saved','proposed','confirmed','failed'].includes(item.status)&&<details><summary>Edit</summary><label>Updated wording<textarea value={wording} maxLength={600} onChange={e=>setWording(e.target.value)}/></label><button disabled={props.busy||wording.trim()===item.draft.text} onClick={()=>props.onUpdate(item,wording)}>Review update</button></details>}
 {item.status!=='deleted'&&<button disabled={props.busy} onClick={()=>props.onForget(item.id)}>{item.status==='deletion-pending'?'Check deletion status':'Forget'}</button>}</article>;
}
export function MemoryPanel(props:Props){return <section className="memory-panel" aria-label="Saved preferences and recipes"><h2>Saved guidance</h2><p>Reused in matching new conversations. Your latest instructions take priority.</p>{props.items.length===0?<p>No preferences saved yet.</p>:props.items.map(item=><MemoryCard key={item.id+item.content_hash} item={item} used={props.usedIds.includes(item.id)} {...props}/>)}</section>}

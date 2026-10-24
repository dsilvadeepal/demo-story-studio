import {api} from '../../shared/api';
import type {Domain,QueryRequest} from '../../shared/types';
import type {Candidate,Comparison,Run,MemoryItem} from './types';
export const scenarios={
 history:()=>api<Candidate[]>('/v1/scenarios/history?include_archived=true'),
 cleanup:(keep_id?:string)=>api<{archived:number}>('/v1/scenarios/history/cleanup',{keep_id:keep_id||null}),
 restoreHistory:(id:string)=>api(`/v1/scenarios/history/${id}/restore`,{}),
 compare:(current:string,candidate:string,query:QueryRequest)=>api<Comparison>('/v1/scenarios/compare',{current_id:current,candidate_id:candidate,query}),
 review:(id:string,kind:string,reason:string,changes_requested=false)=>api(`/v1/scenarios/${id}/review`,{kind,reason,actor:'owner',target:kind==='override'?'warnings':'revision',changes_requested}),
 approve:(candidate:Candidate,active:string)=>api<{id:string}>('/v1/scenarios/approve',{candidate_id:candidate.id,expected_hash:candidate.content_hash,expected_active_id:active}),
 apply:(approval:string,key:string)=>api('/v1/scenarios/apply',{approval_id:approval,key}),
 recover:(target:string,active:string,key:string)=>api('/v1/scenarios/recover',{target_id:target,expected_active_id:active,key,confirmed:true}),
 diff:(id:string,cursor=0,table='')=>api<{changes:{table:string;record_id:string;field:string;before:unknown;after:unknown}[];total:number;next_cursor?:number|null}>(`/v1/scenarios/${id}/diff?page_size=25&cursor=${cursor}&table=${encodeURIComponent(table)}`)
};
export const runs={
 start:(brief:string,domain:Domain,parent_id:string,audience='general',intent='demo preparation',visible?:QueryRequest)=>api<Run>('/v1/runs',{brief,scope:{domain,audience,intent,filters:visible?.filters||{},period:visible?.period||null},parent_id}),
 get:(id:string)=>api<Run>(`/v1/runs/${id}`),
 resume:(run:Run,kind:string,text:string)=>api<Run>(`/v1/runs/${run.id}/resume`,{kind,text,interrupt_id:run.interrupt_id}),
 cancel:(id:string)=>api<Run>(`/v1/runs/${id}/cancel`,{})
};

export const memories={
 list:()=>api<MemoryItem[]>('/v1/memory'),
 propose:(draft:MemoryItem['draft'])=>api<MemoryItem>('/v1/memory/propose',draft),
 confirm:(item:MemoryItem)=>api<MemoryItem>(`/v1/memory/${item.id}/confirm`,{content_hash:item.content_hash}),
 save:(id:string)=>api<MemoryItem>(`/v1/memory/${id}/save`,{}),
 update:(id:string,draft:MemoryItem['draft'])=>api<MemoryItem>(`/v1/memory/${id}`,draft,undefined,'PUT'),
 forget:(id:string)=>api<MemoryItem>(`/v1/memory/${id}/forget`,{confirmed:true}),
 outcome:(revision_id:string,successful:boolean)=>api('/v1/memory/outcome',{revision_id,successful}),
 ignore:(run_id:string,id:string)=>api<Run>(`/v1/runs/${run_id}/ignore-memory`,{ids:[id]})
};

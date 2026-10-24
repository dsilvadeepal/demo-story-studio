import type {QueryRequest,QueryResponse} from './types';
export async function api<T>(path:string,body?:unknown,signal?:AbortSignal,method?:'PUT'):Promise<T>{
 const r=await fetch('/api'+path,{method:method||(body===undefined?'GET':'POST'),headers:{'Content-Type':'application/json'},credentials:'same-origin',body:body===undefined?undefined:JSON.stringify(body),signal});
 if(!r.ok){const e=await r.json().catch(()=>({detail:'Request failed'}));if(r.status===401)window.dispatchEvent(new Event('studio-session-expired'));throw Object.assign(new Error(r.status===409?'This revision or approval is stale. Reload the current dataset and review again.':typeof e.detail==='string'?e.detail:'Check your filter values and try again.'),{status:r.status,code:e.code});}
 return r.json();
}
export const fetchQuery=(request:QueryRequest,signal:AbortSignal)=>api<QueryResponse>('/v1/query',request,signal);

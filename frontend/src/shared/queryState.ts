import type {Domain,Filters} from './types';
export type WorkspaceState={dashboard:Domain;page:string;filters:Filters};
export const newContext=(dashboard:Domain):WorkspaceState=>({dashboard,page:dashboard==='sales'?'executive':'trend',filters:{}});
export function reducer(s:WorkspaceState,event:{type:'dashboard';dashboard:Domain}|{type:'page';page:string}|{type:'filter';key:string;values:string[]}|{type:'reset'}):WorkspaceState{
 if(event.type==='dashboard')return newContext(event.dashboard);
 if(event.type==='page'){const filters={...s.filters};if(s.dashboard==='sales'&&event.page!=='detail')delete filters.days_bucket;return {...s,page:event.page,filters};}
 if(event.type==='reset')return {...s,filters:{}};
 return {...s,filters:{...s.filters,[event.key]:event.values}};
}

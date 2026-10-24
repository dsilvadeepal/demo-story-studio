export type State={candidateId:string|null;approvalId:string|null;view:'current'|'preview';generation:number};
export const initialState:State={candidateId:null,approvalId:null,view:'current',generation:0};
export type Event={type:'candidate';id:string}|{type:'approved';id:string;candidateId:string;generation:number}|{type:'view';view:State['view']}|{type:'changed'}|{type:'loading'}|{type:'loaded';generation:number;id:string};
export function reduceState(s:State,e:Event):State{
 if(e.type==='candidate')return {...s,candidateId:e.id,approvalId:e.id===s.candidateId?s.approvalId:null,generation:s.generation+(e.id===s.candidateId?0:1)};
 if(e.type==='approved')return e.candidateId===s.candidateId&&e.generation===s.generation?{...s,approvalId:e.id}:s;
 if(e.type==='changed')return {...s,approvalId:null,generation:s.generation+1};
 if(e.type==='view')return {...s,view:e.view,generation:s.generation+1};
 if(e.type==='loading')return {...s,generation:s.generation+1};
 if(e.generation!==s.generation)return s;
 return {...s,candidateId:e.id};
}

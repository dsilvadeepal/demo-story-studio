import {it,expect} from 'vitest';
import {initialState,reduceState} from './state';
it('approval never changes active data and a new candidate clears approval',()=>{
 let state=reduceState(initialState,{type:'candidate',id:'one'});
 state=reduceState(state,{type:'approved',id:'approval',candidateId:'one',generation:state.generation});
 expect(state.approvalId).toBe('approval');expect(state.view).toBe('current');
 state=reduceState(state,{type:'candidate',id:'two'});expect(state.approvalId).toBeNull();
});
it('ignores stale loads and clears approvals when changes are requested',()=>{
 const state={...initialState,generation:2,approvalId:'old'};
 expect(reduceState(state,{type:'loaded',generation:1,id:'stale'})).toEqual(state);
 expect(reduceState(state,{type:'changed'}).approvalId).toBeNull();
});
it('rejects a late approval for a different candidate or changed generation',()=>{
 const a=reduceState(initialState,{type:'candidate',id:'a'});
 const b=reduceState(a,{type:'candidate',id:'b'});
 expect(reduceState(b,{type:'approved',id:'approval-a',candidateId:'a',generation:a.generation} as any).approvalId).toBeNull();
 const changed=reduceState(a,{type:'changed'});
 expect(reduceState(changed,{type:'approved',id:'approval-a',candidateId:'a',generation:a.generation} as any).approvalId).toBeNull();
});

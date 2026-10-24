import {describe,it,expect} from 'vitest';
import {newContext,reducer} from './queryState';
describe('workspace query context',()=>{
 it('resets incompatible filters when switching dashboards',()=>{
  let s=newContext('sales'); s=reducer(s,{type:'filter',key:'account_type',values:['Enterprise']});
  expect(reducer(s,{type:'dashboard',dashboard:'service'}).filters).toEqual({});
 });
 it('retains compatible filters on page navigation',()=>{
  let s=newContext('sales');s=reducer(s,{type:'filter',key:'industry',values:['Technology']});
  expect(reducer(s,{type:'page',page:'pipeline'}).filters.industry).toEqual(['Technology']);
 });
});
it('clears the Detail-only days bucket while preserving visible Sales filters',()=>{
 let s=reducer(newContext('sales'),{type:'page',page:'detail'});
 s=reducer(s,{type:'filter',key:'days_bucket',values:['>6 months']});
 s=reducer(s,{type:'filter',key:'industry',values:['Technology']});
 s=reducer(s,{type:'page',page:'executive'});
 expect(s.filters.days_bucket).toBeUndefined();expect(s.filters.industry).toEqual(['Technology']);
});

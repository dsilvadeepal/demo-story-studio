import {it,expect,vi,afterEach} from 'vitest';
import {renderHook,act,waitFor,cleanup} from '@testing-library/react';
import {useQuery} from './useQuery';
import type {QueryRequest} from './types';
afterEach(()=>{cleanup();vi.unstubAllGlobals()});
it('does not allow a delayed obsolete response to replace the latest filters',async()=>{
 const pending:((v:unknown)=>void)[]=[];
 vi.stubGlobal('fetch',vi.fn(()=>new Promise(resolve=>pending.push(resolve))));
 const base:QueryRequest={dashboard:'sales',dataset_id:'baseline',semantic_version:'1.0.0',filters:{}};
 const {result,rerender}=renderHook(({req})=>useQuery(req),{initialProps:{req:base}});
 rerender({req:{...base,filters:{industry:['Technology']}}});
 await act(async()=>pending[1]({ok:true,json:async()=>({values:{total_sales:'200'}})}));
 await waitFor(()=>expect(result.current.data?.values.total_sales).toBe('200'));
 await act(async()=>pending[0]({ok:true,json:async()=>({values:{total_sales:'100'}})}));
 expect(result.current.data?.values.total_sales).toBe('200');
});

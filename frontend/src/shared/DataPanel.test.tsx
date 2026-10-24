import {it,expect,vi} from 'vitest';
import {render,screen,cleanup} from '@testing-library/react';
import {DataPanel} from './DataPanel';
vi.mock('./Chart',()=>({Chart:()=>null}));
vi.mock('./useQuery',()=>({useQuery:()=>({data:{row_count:960,groups:Array.from({length:500},(_,i)=>({key:String(i),values:{weighted_pipeline:1},record_ids:[String(i)]})),values:{},warnings:['Grouped output limited to 500; narrow the filters.'],revision:1,query_id:'test'},retry:()=>{}})}));
it('makes the group cap visible without opening metric details',()=>{
 render(<DataPanel request={{dashboard:'sales',dataset_id:'baseline',semantic_version:'1.0.0',filters:{}}} spec={{title:'Expected close',metric:'weighted_pipeline',dimension:'close_date',kind:'scatter'}} metrics={[]} onInspect={()=>{}}/>);
 expect(screen.getByRole('status').textContent).toContain('Grouped output limited to 500');
 expect(screen.getByText(/500 groups.*960 eligible records/)).toBeTruthy();cleanup();
});

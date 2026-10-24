import {useState,useEffect} from 'react';
import {it,expect,vi,afterEach} from 'vitest';
import {render,screen,fireEvent,cleanup,waitFor} from '@testing-library/react';
import {CustomizationBoundary} from './CustomizationBoundary';
import {scenarios,runs,memories} from './api';
import {api} from '../../shared/api';
vi.mock('./api',()=>({scenarios:{history:vi.fn(),compare:vi.fn(),diff:vi.fn(),review:vi.fn(),approve:vi.fn(),apply:vi.fn()},runs:{get:vi.fn(),start:vi.fn(),resume:vi.fn()},memories:{list:vi.fn().mockResolvedValue([]),propose:vi.fn(),confirm:vi.fn(),save:vi.fn()}}));
vi.mock('../../shared/api',()=>({api:vi.fn()}));
function Evidence({manifest,catalog}:any){const [page,setPage]=useState('Executive');return <><button onClick={()=>setPage('Pipeline')}>Choose pipeline</button><p>{page} page</p><p data-testid="dataset">{manifest.id} / {catalog.options.sales.stage[0]}</p></>}
const active={id:'base',as_of_date:'2026-10-21',revision:1,semantic_version:'1.0.0' as const,counts:{}};
const catalog={options:{sales:{stage:['Prospecting']},service:{}},metrics:{sales:[],service:[]},dimensions:{sales:[],service:[]}};
const candidate={id:'candidate',parent_id:'base',revision:2,content_hash:'hash',as_of_date:'2026-10-21',status:'preview' as const};
afterEach(()=>{cleanup();localStorage.clear();vi.clearAllMocks()});
it('restores pending review and uses candidate manifest and catalog together',async()=>{
 localStorage.setItem('studio-run-sales','run');
 vi.mocked(runs.get).mockResolvedValue({id:'run',parent_id:'base',status:'paused',version:1,interrupt_id:'review',result:{review_state:{candidate}}});
 vi.mocked(scenarios.history).mockResolvedValue([candidate]);
 vi.mocked(scenarios.compare).mockResolvedValue({current_id:'base',candidate_id:'candidate',metric_deltas:{},changed_counts:{},warnings:[]});
 vi.mocked(scenarios.diff).mockResolvedValue({changes:[],total:0});
 vi.mocked(scenarios.approve).mockResolvedValue({id:'approval'});
 vi.mocked(api).mockImplementation(async path=>path.includes('/dataset')?{...active,id:'candidate',revision:2}:{...catalog,options:{sales:{stage:['Qualification']},service:{}}} as any);
 render(<CustomizationBoundary domain="sales" active={active} catalog={catalog} onActivated={async()=>{}}>{ctx=><>{ctx.review}<Evidence {...ctx}/></>}</CustomizationBoundary>);
 fireEvent.click(await screen.findByText('Review changes · revision 2'));
 expect(await screen.findByRole('button',{name:'Approve & apply revision 2'})).toBeTruthy();
 await waitFor(()=>expect((screen.getByRole('button',{name:'Approve & apply revision 2'}) as HTMLButtonElement).disabled).toBe(false));
 fireEvent.click(screen.getByRole('button',{name:'Approve & apply revision 2'}));
 await waitFor(()=>expect(scenarios.approve).toHaveBeenCalledWith(candidate,'base'));
 await waitFor(()=>expect(screen.getByTestId('dataset').textContent).toBe('base / Prospecting'));
 await waitFor(()=>expect(scenarios.apply).toHaveBeenCalledWith('approval','apply:approval'));expect(runs.start).not.toHaveBeenCalled();
 fireEvent.click(screen.getByRole('button',{name:'Choose pipeline'}));
 fireEvent.click(screen.getByRole('button',{name:'Preview revision 2'}));
 await waitFor(()=>expect(screen.getByTestId('dataset').textContent).toBe('candidate / Qualification'));
 expect(screen.getByText('Pipeline page')).toBeTruthy();
 expect(vi.mocked(scenarios.compare).mock.calls[0][2].filters).toEqual({});
});
function setupReview(){
 localStorage.setItem('studio-run-sales','run');
 vi.mocked(runs.get).mockResolvedValue({id:'run',parent_id:'base',status:'paused',version:1,interrupt_id:'review',result:{review_state:{candidate}}});
 vi.mocked(scenarios.history).mockResolvedValue([candidate,{...candidate,id:'other',revision:3}]);
 vi.mocked(scenarios.compare).mockResolvedValue({current_id:'base',candidate_id:'candidate',metric_deltas:{},changed_counts:{},warnings:[]});
 vi.mocked(scenarios.diff).mockResolvedValue({changes:[],total:0});
}
it('refreshes authoritative active context after a stale approval rejection',async()=>{
 setupReview();const refresh=vi.fn().mockResolvedValue(undefined);
 vi.mocked(scenarios.approve).mockRejectedValue(Object.assign(new Error('Stale revision'),{status:409,code:'STALE_VERSION'}));
 render(<CustomizationBoundary domain="sales" active={active} catalog={catalog} onActivated={refresh}>{ctx=><>{ctx.review}<Evidence {...ctx}/></>}</CustomizationBoundary>);
 fireEvent.click(await screen.findByText('Review changes · revision 2'));
 const button=await screen.findByRole('button',{name:'Approve & apply revision 2'});
 await waitFor(()=>expect((button as HTMLButtonElement).disabled).toBe(false));fireEvent.click(button);
 await waitFor(()=>expect(refresh).toHaveBeenCalledOnce());
 expect(scenarios.apply).not.toHaveBeenCalled();
});
it('blocks history selection while a deferred approval is pending',async()=>{
 setupReview();let resolve!:(v:{id:string})=>void;
 vi.mocked(scenarios.approve).mockReturnValue(new Promise(r=>{resolve=r}));
 render(<CustomizationBoundary domain="sales" active={active} catalog={catalog} onActivated={async()=>{}}>{ctx=><>{ctx.review}<Evidence {...ctx}/></>}</CustomizationBoundary>);
 fireEvent.click(await screen.findByText('Review changes · revision 2'));
 const button=await screen.findByRole('button',{name:'Approve & apply revision 2'});
 await waitFor(()=>expect((button as HTMLButtonElement).disabled).toBe(false));fireEvent.click(button);
 expect((screen.getByRole('button',{name:'Revision 3 · preview'}) as HTMLButtonElement).disabled).toBe(true);
 resolve({id:'approval'});
 await waitFor(()=>expect(scenarios.apply).toHaveBeenCalledWith('approval','apply:approval'));
});
it('allows reading the next page of field changes',async()=>{
 setupReview();vi.mocked(scenarios.diff).mockResolvedValueOnce({changes:[{table:'cases',record_id:'first',field:'closed_date',before:'old',after:'new'}],total:26,next_cursor:25} as any).mockResolvedValueOnce({changes:[{table:'cases',record_id:'last',field:'closed_date',before:'old',after:'new'}],total:26,next_cursor:null} as any);
 render(<CustomizationBoundary domain="sales" active={active} catalog={catalog} onActivated={async()=>{}}>{ctx=><>{ctx.review}<Evidence {...ctx}/></>}</CustomizationBoundary>);
 fireEvent.click(await screen.findByText('Review changes · revision 2'));
 fireEvent.click(await screen.findByRole('button',{name:'Next changes'}));
 await waitFor(()=>expect(scenarios.diff).toHaveBeenLastCalledWith('candidate',25,''));
 expect(await screen.findByText(/last · closed_date/)).toBeTruthy();
});

function ScopedEvidence({onQuery}:any){useEffect(()=>onQuery({dataset_id:'base',semantic_version:'1.0.0',dashboard:'sales',filters:{account:['Selected account']},period:{start:'2026-10-01',end:'2026-10-21',field:'close_date'}}),[onQuery]);return <p>Scoped dashboard</p>}
it('submits the visible cohort unless the owner explicitly selects the entire dataset',async()=>{
 HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','')};HTMLDialogElement.prototype.close=function(){this.removeAttribute('open')};
 vi.mocked(scenarios.history).mockResolvedValue([]);
 vi.mocked(runs.start).mockResolvedValue({id:'new',parent_id:'base',status:'failed',version:1,interrupt_id:null,result:{}});
 render(<CustomizationBoundary domain="sales" active={active} catalog={catalog} onActivated={async()=>{}}>{ctx=><>{ctx.review}<ScopedEvidence {...ctx}/></>}</CustomizationBoundary>);
 fireEvent(window,new Event('studio-customize'));
 fireEvent.change(screen.getByLabelText('Your brief'),{target:{value:'Adjust the top five displayed deals'}});
 fireEvent.click(screen.getByRole('button',{name:'Prepare preview'}));
 await waitFor(()=>expect(runs.start).toHaveBeenCalled());
 expect(vi.mocked(runs.start).mock.calls[0][5]).toMatchObject({filters:{account:['Selected account']},period:{start:'2026-10-01'}});
 fireEvent(window,new Event('studio-customize'));
 fireEvent.change(screen.getByLabelText('Your brief'),{target:{value:'Globally refresh both domains'}});
 fireEvent.click(screen.getByRole('checkbox',{name:'Use the entire dataset instead of the visible filters and dates'}));
 fireEvent.click(screen.getByRole('button',{name:'Prepare preview'}));
 await waitFor(()=>expect(runs.start).toHaveBeenCalledTimes(2));
 expect(vi.mocked(runs.start).mock.calls[1][5]).toMatchObject({filters:{},period:undefined});
});

it('filters text differences by category and resets pagination',async()=>{
 setupReview();
 render(<CustomizationBoundary domain="sales" active={active} catalog={catalog} onActivated={async()=>{}}>{ctx=><>{ctx.review}<Evidence {...ctx}/></>}</CustomizationBoundary>);
 const select=await screen.findByLabelText('Change category');
 fireEvent.change(select,{target:{value:'opportunities'}});
 await waitFor(()=>expect(scenarios.diff).toHaveBeenLastCalledWith('candidate',0,'opportunities'));
});
it('reports an apply failure without claiming activation',async()=>{
 setupReview();const refresh=vi.fn();
 vi.mocked(scenarios.approve).mockResolvedValue({id:'approval'});
 vi.mocked(scenarios.apply).mockRejectedValueOnce(new Error('Apply unavailable'));
 render(<CustomizationBoundary domain="sales" active={active} catalog={catalog} onActivated={refresh}>{ctx=><>{ctx.review}<Evidence {...ctx}/></>}</CustomizationBoundary>);
 fireEvent.click(await screen.findByText('Review changes · revision 2'));
 const button=await screen.findByRole('button',{name:'Approve & apply revision 2'});
 await waitFor(()=>expect((button as HTMLButtonElement).disabled).toBe(false));fireEvent.click(button);
 expect((await screen.findAllByRole('alert')).some(e=>e.textContent==='Apply unavailable')).toBe(true);
 expect(refresh).not.toHaveBeenCalled();fireEvent.click(screen.getByRole('button',{name:'Current'}));await waitFor(()=>expect(screen.getByTestId('dataset').textContent).toBe('base / Prospecting'));
});

it('keeps the refinement request visible and compares the new preview with the previous preview',async()=>{
 setupReview();const next={...candidate,id:'refined',revision:3};
 vi.mocked(api).mockImplementation(async path=>path.includes('/dataset')?{...active,id:path.includes('refined')?'refined':'candidate',revision:3}:catalog as any);
 vi.mocked(scenarios.review).mockResolvedValue({});
 vi.mocked(runs.resume).mockResolvedValue({id:'run',parent_id:'base',status:'paused',version:2,interrupt_id:'next-review',result:{review_state:{candidate:next}}});
 vi.mocked(scenarios.compare).mockImplementation(async(current,id)=>({current_id:current,candidate_id:id,metric_deltas:{},changed_counts:(current==='candidate'?{'opportunities.name':1200}:{}) as Record<string,number>,warnings:[]}));
 render(<CustomizationBoundary domain="sales" active={active} catalog={catalog} onActivated={async()=>{}}>{ctx=><>{ctx.review}<Evidence {...ctx}/></>}</CustomizationBoundary>);
 fireEvent.click(await screen.findByRole('button',{name:'Refine preview'}));
 fireEvent.change(screen.getByLabelText('Review note or requested change'),{target:{value:'Use installation project names'}});
 fireEvent.click(screen.getByRole('button',{name:'Request changes'}));
 await waitFor(()=>expect(screen.queryByRole('dialog')).toBeNull());

 expect(await screen.findByText('opportunities.name: 1,200 fields changed')).toBeTruthy();
 await waitFor(()=>expect(screen.getByTestId('dataset').textContent).toContain('refined'));
 expect(scenarios.compare).toHaveBeenCalledWith('candidate','refined',expect.objectContaining({filters:{}}));
 expect(scenarios.apply).not.toHaveBeenCalled();

 expect(screen.queryByRole('dialog')).toBeNull();
});

it('shows a refinement clarification inside the drawer and resumes the same run',async()=>{
 setupReview();vi.mocked(scenarios.review).mockResolvedValue({});
 vi.mocked(runs.resume).mockResolvedValueOnce({id:'run',parent_id:'base',status:'paused',version:2,interrupt_id:'clarification',result:{interrupt:{kind:'clarification',question:'Which region should change?'}}});
 render(<CustomizationBoundary domain="sales" active={active} catalog={catalog} onActivated={async()=>{}}>{ctx=><>{ctx.review}<Evidence {...ctx}/></>}</CustomizationBoundary>);
 fireEvent.click(await screen.findByRole('button',{name:'Refine preview'}));
 fireEvent.change(screen.getByLabelText('Review note or requested change'),{target:{value:'Change the region'}});
 fireEvent.click(screen.getByRole('button',{name:'Request changes'}));
 const input=await screen.findByLabelText('Your clarification');
 expect(screen.getByRole('dialog').contains(input)).toBe(true);
 expect(screen.queryByRole('button',{name:'Request changes'})).toBeNull();
 vi.mocked(runs.resume).mockResolvedValueOnce({id:'run',parent_id:'base',status:'queued',version:3,interrupt_id:null,result:{}});
 fireEvent.change(input,{target:{value:'Change region Central to Montréal Centre.'}});
 fireEvent.click(screen.getByRole('button',{name:'Continue with clarification'}));
 await waitFor(()=>expect(runs.resume).toHaveBeenLastCalledWith(expect.objectContaining({id:'run'}),'clarify','Change region Central to Montréal Centre.'));
 expect(scenarios.apply).not.toHaveBeenCalled();
});

it('saves the exact entered preference through confirmation before remote save',async()=>{
 setupReview();const item={id:'preference',content_hash:'exact-text-hash',status:'proposed'} as any;
 vi.mocked(memories.propose).mockResolvedValue(item);vi.mocked(memories.confirm).mockResolvedValue({...item,status:'confirmed'});vi.mocked(memories.save).mockResolvedValue({...item,status:'saved'});
 render(<CustomizationBoundary domain="sales" active={active} catalog={catalog} onActivated={async()=>{}}>{()=>null}</CustomizationBoundary>);
 fireEvent.click(screen.getByText('Demo memory'));
 fireEvent.change(screen.getByLabelText('Preference',{exact:true}),{target:{value:'Use customer-friendly HVAC terminology.'}});
 fireEvent.click(screen.getByRole('button',{name:'Save preference',exact:true}));
 await waitFor(()=>expect(memories.save).toHaveBeenCalledWith('preference'));
 expect(memories.confirm).toHaveBeenCalledWith(item);
 expect(vi.mocked(memories.propose).mock.calls[0][0].text).toBe('Use customer-friendly HVAC terminology.');
 expect(vi.mocked(memories.confirm).mock.invocationCallOrder[0]).toBeLessThan(vi.mocked(memories.save).mock.invocationCallOrder[0]);
 expect(await screen.findByText(/Saved. Start a new customization/)).toBeTruthy();
 expect(scenarios.apply).not.toHaveBeenCalled();
});

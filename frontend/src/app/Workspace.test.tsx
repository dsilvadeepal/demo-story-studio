import {it,expect,vi} from 'vitest';
import {render,screen,fireEvent,cleanup} from '@testing-library/react';
import {Workspace} from './Workspace';
vi.mock('../shared/DataPanel',()=>({KPI:()=>null,DataPanel:({spec,request,onInspect}:any)=><button onClick={()=>onInspect('Enterprise',spec,request)}>Inspect {spec.title}</button>}));
vi.mock('../shared/Records',()=>({Records:()=>null}));
it('invalidates selected evidence when period or breakdown changes',()=>{
 const manifest={id:'baseline',as_of_date:'2026-10-21',revision:1,semantic_version:'1.0.0' as const,counts:{},presentation:{}};
 const catalog={options:{sales:{stage:['Prospecting'],account_type:['Enterprise']},service:{}},metrics:{sales:[],service:[]},dimensions:{sales:[],service:[]}};
 render(<Workspace domain="sales" manifest={manifest} catalog={catalog} onBack={()=>{}}/>);
 fireEvent.click(screen.getByRole('button',{name:'Inspect Conversion by dimension'}));expect(screen.getByRole('heading',{name:'Evidence: Enterprise'})).toBeTruthy();
 fireEvent.change(screen.getByLabelText('Period start'),{target:{value:'2026-10-01'}});
 expect(screen.queryByRole('heading',{name:'Evidence: Enterprise'})).toBeNull();
 fireEvent.click(screen.getByRole('button',{name:'Inspect Conversion by dimension'}));
 fireEvent.change(screen.getByRole('combobox',{name:'Break down conversion by'}),{target:{value:'industry'}});
 expect(screen.queryByRole('heading',{name:'Evidence: Enterprise'})).toBeNull();cleanup();
});
it('preserves an explicit absolute period through refreshed previews and back',()=>{
 const manifest={id:'baseline',as_of_date:'2026-10-21',revision:1,semantic_version:'1.0.0' as const,counts:{},presentation:{}};
 const catalog={options:{sales:{stage:['Prospecting'],account_type:['Enterprise']},service:{}},metrics:{sales:[],service:[]},dimensions:{sales:[],service:[]}};
 const props={domain:'sales' as const,manifest,catalog,onBack:()=>{}};
 const view=render(<Workspace {...props}/>);
 fireEvent.change(screen.getByLabelText('Period start'),{target:{value:'2026-10-01'}});
 view.rerender(<Workspace {...props} manifest={{...manifest,id:'refresh',as_of_date:'2027-01-19',revision:2}}/>);
 expect((screen.getByLabelText('Period start') as HTMLInputElement).value).toBe('2026-10-01');
 expect((screen.getByLabelText('Period end') as HTMLInputElement).value).toBe('2026-10-21');
 view.rerender(<Workspace {...props}/>);
 expect((screen.getByLabelText('Period start') as HTMLInputElement).value).toBe('2026-10-01');cleanup();
});
it('uses revision-specific industry titles and restores canonical headings',()=>{
 const manifest={id:'baseline',as_of_date:'2026-10-21',revision:1,semantic_version:'1.0.0' as const,counts:{},presentation:{}};
 const catalog={options:{sales:{stage:['Prospecting'],account_type:['Enterprise']},service:{}},metrics:{sales:[],service:[]},dimensions:{sales:[],service:[]}};
 const props={domain:'sales' as const,manifest,catalog,onBack:()=>{}};
 const view=render(<Workspace {...props}/>);
 const original=screen.getByRole('heading',{level:1}).textContent;
 view.rerender(<Workspace {...props} preview manifest={{...manifest,id:'manufacturing',revision:2,presentation:{industry:'Manufacturing',page_titles:{executive:'Manufacturing sales overview',pipeline:'Equipment sales pipeline'}}}}/>);
 expect(screen.getByRole('heading',{name:'Manufacturing sales overview'})).toBeTruthy();
 expect(screen.getByText(/Metric definitions unchanged/)).toBeTruthy();
 fireEvent.click(screen.getByRole('button',{name:'Pipeline Analysis'}));
 expect(screen.getByRole('heading',{name:'Equipment sales pipeline'})).toBeTruthy();
 view.rerender(<Workspace {...props}/>);
 expect(screen.queryByRole('heading',{name:'Equipment sales pipeline'})).toBeNull();
 fireEvent.click(screen.getByRole('button',{name:'Executive Summary'}));
 expect(screen.getByRole('heading',{level:1}).textContent).toBe(original);cleanup();
});
it('highlights the current workflow stage including preview and the combined final step',()=>{
 const props={domain:'sales' as const,manifest:{id:'baseline',as_of_date:'2026-10-21',revision:1,semantic_version:'1.0.0' as const,counts:{}},catalog:{options:{sales:{stage:[]},service:{}},metrics:{sales:[],service:[]},dimensions:{sales:[],service:[]}},onBack:()=>{}};
 const view=render(<Workspace {...props}/>);
 expect(screen.getByText('2 Inspect').getAttribute('aria-current')).toBe('step');
 view.rerender(<Workspace {...props} preview/>);
 expect(screen.getByText('4 Preview & iterate').getAttribute('aria-current')).toBe('step');
 expect(screen.getByText('2 Inspect').getAttribute('aria-current')).toBeNull();
 for(const step of [3,5]){view.rerender(<Workspace {...props} preview step={step}/>);expect(screen.getByText(step===3?'3 Describe':'5 Approve & apply').getAttribute('aria-current')).toBe('step')}
 expect(screen.queryByText('6 Apply')).toBeNull();cleanup();
});
it('reports renamed filter values that are reset when switching revision',()=>{
 const manifest={id:'base',as_of_date:'2026-10-21',revision:1,semantic_version:'1.0.0' as const,counts:{}};
 const catalog={options:{sales:{stage:[]},service:{division:['Central'],type:['Order']}},metrics:{sales:[],service:[]},dimensions:{sales:[],service:[]}};
 const view=render(<Workspace domain="service" manifest={manifest} catalog={catalog} onBack={()=>{}}/>);
 fireEvent.click(screen.getByLabelText('Central'));
 fireEvent.click(screen.getByRole('button',{name:'Breakdown'}));
 view.rerender(<Workspace domain="service" manifest={{...manifest,id:'new',revision:2}} catalog={{...catalog,options:{...catalog.options,service:{division:['Laval'],type:['Order']}}}} onBack={()=>{}} preview/>);
 expect(screen.getByText(/Filters reset for this revision: division/)).toBeTruthy();
 expect(screen.getByRole('button',{name:'Breakdown'}).getAttribute('aria-current')).toBe('page');cleanup();
});

import {useReducer,useState,useEffect,useRef,type ReactNode} from 'react';
import type {Domain,Manifest,Catalog,QueryRequest} from '../shared/types';
import type {ChartSpec} from '../shared/pageTypes';
import {newContext,reducer} from '../shared/queryState';
import {salesPages} from '../features/sales/config';
import {servicePages} from '../features/service/config';
import {Filters} from '../shared/Filters';
import {DataPanel,KPI} from '../shared/DataPanel';
import {Records} from '../shared/Records';
import {RecordDrawer} from '../shared/RecordDrawer';
export function Workspace({domain,manifest,catalog,onBack,onQuery,preview=false,review,step}:{domain:Domain;manifest:Manifest;catalog:Catalog;onBack:()=>void;onQuery?:(q:QueryRequest)=>void;preview?:boolean;review?:ReactNode;step?:number}){
 const defaultStart=()=>{const d=new Date(manifest.as_of_date+'T00:00:00Z');d.setUTCMonth(d.getUTCMonth()-18);return d.toISOString().slice(0,10)};
 const [state,dispatch]=useReducer(reducer,newContext(domain));const [dimension,setDimension]=useState('account_type');const [start,setStart]=useState(defaultStart),[end,setEnd]=useState(manifest.as_of_date);
 const [filterNotice,setFilterNotice]=useState('');
 const [record,setRecord]=useState<string|null>(null);const [evidence,setEvidence]=useState<{request:QueryRequest;label:string}|null>(null);
 useEffect(()=>setEvidence(null),[start,end,dimension]);
 const pages=domain==='sales'?salesPages:servicePages;const page=pages[state.page];const metrics=catalog.metrics[domain];
 const base:QueryRequest={dataset_id:manifest.id,semantic_version:manifest.semantic_version,dashboard:domain,filters:state.filters};
 const previous=useRef(manifest.id);
 useEffect(()=>{if(previous.current!==manifest.id){setRecord(null);setEvidence(null);const removed:string[]=[];for(const [key,values] of Object.entries(state.filters)){const allowed=catalog.options[domain][key]||[];const kept=values.filter(v=>allowed.includes(v));if(kept.length!==values.length)removed.push(key.replaceAll('_',' '));dispatch({type:'filter',key,values:kept})}setFilterNotice(removed.length?'Filters reset for this revision: '+removed.join(', ')+'. Other filters and the selected page were retained.':'');previous.current=manifest.id}},[manifest.id]);
 const invalidDates=start>end;
 const period=domain==='sales'&&state.page!=='detail'?{start,end,field:state.page==='executive'?'close_date' as const:'created_at' as const}:undefined;
 const req:QueryRequest={...base,...(period?{period}:{} )};
 useEffect(()=>{onQuery?.(req)},[JSON.stringify(req),onQuery]);
 const openStages=catalog.options.sales.stage.filter(s=>!s.includes('Closed'));
 function inspect(key:string|string[],spec:ChartSpec,request:QueryRequest){
  if(spec.dimension==='close_date'&&Array.isArray(key)){setRecord(key[1]);return;}
  const supported=catalog.options[domain][spec.dimension];
  let r={...request,filters:{...request.filters}};
  if(supported&&!Array.isArray(key))r.filters[spec.dimension]=[key];
  else if(spec.dimension==='week_origin'&&Array.isArray(key)){
   const until=new Date(key[0]+'T00:00:00Z');until.setUTCDate(until.getUTCDate()+6);
   r={...r,period:{start:key[0],end:until.toISOString().slice(0,10),field:'created_at'}};
  }
  setEvidence({request:r,label:Array.isArray(key)?key.join(' · '):key});
 }
 return <main className="workspace"><div className="flow-bar"><button className="text-button" onClick={onBack}>← Studio</button><div className="steps" aria-label="Workflow progress">{['Choose','Inspect','Describe','Preview & iterate','Approve & apply'].map((label,i)=>i+1===(step??(preview?4:2))?<strong key={label} aria-current="step">{i+1} {label}</strong>:<span key={label}>{i+1} {label}</span>)}</div><span className="preview-label">Review before applying</span></div>
 <div className="workspace-heading"><div><span className="eyebrow">{domain.toUpperCase()} / {preview?'PREVIEW DATASET':'CURRENT DATASET'}</span><h1>{manifest.presentation?.page_titles?.[state.page]||page.title}</h1><p>{page.subtitle}</p>{manifest.presentation?.industry&&<p>{manifest.presentation.industry} demo · {page.title} · Metric definitions unchanged</p>}</div><button className="primary" onClick={()=>window.dispatchEvent(new CustomEvent('studio-customize',{detail:{domain}}))}>Customize this dashboard <span>✧</span></button></div>
 <div className="dataset-line"><span className="dot"/> Synthetic dataset · as of {manifest.as_of_date}<span>Revision {manifest.revision}</span><span>Evidence matches selected revision</span></div>
 <nav className="page-tabs" aria-label="Dashboard pages">{Object.entries(pages).map(([key,p])=><button key={key} aria-current={key===state.page?'page':undefined} onClick={()=>{dispatch({type:'page',page:key});setEvidence(null)}}>{key==='executive'?'Executive Summary':key==='pipeline'?'Pipeline Analysis':key==='detail'?'Detail Analysis':key==='trend'?'Trend':'Breakdown'}</button>)}</nav>
 {filterNotice&&<p role="status" className="filter-notice">{filterNotice}</p>}{review}
 <Filters keys={domain==='sales'?['account','account_type','industry','type','owner',...(state.page==='detail'?['days_bucket']:[])]:['priority','type','division','owner','industry']} options={catalog.options[domain]} values={state.filters} onChange={(key,values)=>{dispatch({type:'filter',key,values});setEvidence(null)}} onReset={()=>{dispatch({type:'reset'});setStart(defaultStart());setEnd(manifest.as_of_date);setEvidence(null)}}/>
 {period&&<div className="period-strip"><span>{period.field==='close_date'?'Close date':'Created date'}</span><label>From <input aria-label="Period start" type="date" value={start} onChange={e=>setStart(e.target.value)}/></label><label>Through <input aria-label="Period end" type="date" value={end} onChange={e=>setEnd(e.target.value)}/></label><small>Chart-specific date exclusions are labeled below.</small></div>}
 {invalidDates?<p role="alert">Choose an end date on or after the start date.</p>:<><div className="kpi-grid">{page.kpis.map(id=><KPI key={id} metric={metrics.find(m=>m.id===id)!} request={req}/>)}</div>
 {state.page==='executive'&&<label className="dimension-picker">Break down conversion by <select value={dimension} onChange={e=>setDimension(e.target.value)}>{['account_type','account','industry','family','product','owner'].map(d=><option key={d} value={d}>{d.replaceAll('_',' ')}</option>)}</select></label>}
 <div className="chart-grid">{page.charts.map((spec,i)=>{
  const s=spec.title==='Conversion by dimension'?{...spec,dimension}:spec;
  const request:QueryRequest={...(s.ignorePeriod?base:req),metric_ids:s.kind==='table'?['created_cases','closed_cases','close_days']:[s.metric],dimension:s.dimension};
  if(s.openOnly)request.filters={...request.filters,stage:openStages};
  return <DataPanel key={state.page+i} spec={s} request={request} metrics={metrics} onInspect={inspect}/>;
 })}{page.records&&<Records request={domain==='sales'?{...base,filters:{...base.filters,stage:openStages}}:base} onOpen={setRecord}/>}</div></>}
 {evidence&&<section className="evidence-section"><div className="section-heading"><h2>Evidence: {evidence.label}</h2><button onClick={()=>setEvidence(null)}>Close evidence</button></div><Records request={evidence.request} onOpen={setRecord}/></section>}
 <footer className="workspace-footer">Synthetic data · No Salesforce or Tableau writes · Metrics calculated by the shared read-only API</footer>
 {record&&previous.current===manifest.id&&<RecordDrawer id={record} domain={domain} datasetId={manifest.id} onClose={()=>setRecord(null)}/>}
 </main>;
}

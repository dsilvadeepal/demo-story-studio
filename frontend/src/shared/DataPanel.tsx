import {useState} from 'react';
import {useQuery} from './useQuery';
import {Chart} from './Chart';
import {format} from './format';
import type {QueryRequest,Metric} from './types';
import type {ChartSpec} from './pageTypes';
export function DataPanel({request,spec,metrics,onInspect}:{request:QueryRequest;spec:ChartSpec;metrics:Metric[];onInspect:(key:string|string[],spec:ChartSpec,request:QueryRequest)=>void}){
 const [table,setTable]=useState(spec.kind==='table');const result=useQuery(request);const metric=metrics.find(m=>m.id===spec.metric);
 return <section className={'panel '+(spec.wide?'wide':'')}><div className="panel-title"><div><h3>{spec.title}</h3><p>{spec.description||metric?.definition}{spec.ignorePeriod?' · Date filter excluded':''}</p></div><button className="icon-button" onClick={()=>setTable(v=>!v)} aria-label={'Toggle data table for '+spec.title}>{table?'Chart':'Table'}</button></div>
 {result.error?<div className="query-message" role="alert">{result.error}<button onClick={result.retry}>Retry</button></div>:!result.data?<div className="skeleton" role="status">Loading chart…</div>:<>
 {result.data.warnings.filter(w=>w.includes('limited')).map(w=><p key={w} className="limit-notice" role="status">{w} Use the record table for all results.</p>)}
 {result.data.row_count===0?<div className="query-message">No records match these filters.</div>:table?<div className="table-wrap chart-table"><table><thead><tr><th scope="col">{spec.dimension.replaceAll('_',' ')}</th>{(spec.kind==='table'?['created_cases','closed_cases','close_days']:[spec.metric]).map(k=><th key={k}>{metrics.find(m=>m.id===k)?.label||k}</th>)}</tr></thead><tbody>{result.data.groups.map((g,i)=><tr key={i}><td><button className="text-button" onClick={()=>onInspect(g.key,spec,{...request,filters:{...request.filters,id:g.record_ids}})}>{Array.isArray(g.key)?g.key.join(' · '):g.key}</button></td>{(spec.kind==='table'?['created_cases','closed_cases','close_days']:[spec.metric]).map(k=><td key={k}>{format(g.values[k],metrics.find(m=>m.id===k)?.unit)}</td>)}</tr>)}</tbody></table></div>:<Chart data={result.data} spec={spec} onInspect={key=>onInspect(key,spec,{...request,filters:{...request.filters,id:result.data!.groups.find(g=>JSON.stringify(g.key)===JSON.stringify(key))!.record_ids}})}/>}
 <div className="panel-foot"><span>{result.data.groups.length.toLocaleString()} groups · {result.data.row_count.toLocaleString()} eligible records · {request.period?`${request.period.start} — ${request.period.end}`:'Full history'}</span><details><summary>Metric details</summary><p>{metric?.definition}. Dataset revision {result.data.revision}. Query {result.data.query_id}.</p>{result.data.warnings.map(w=><p key={w}>{w}</p>)}</details></div></>}
 </section>;
}
export function KPI({request,metric}:{request:QueryRequest;metric:Metric}){
 const result=useQuery({...request,metric_ids:[metric.id]});const value=result.data?.values[metric.id];const previous=result.data?.previous?.[metric.id];
 const delta=value!==null&&value!==undefined&&previous!==null&&previous!==undefined&&Number(previous)!==0?(Number(value)-Number(previous))/Math.abs(Number(previous)):null;
 return <article className="kpi"><span>{metric.label}</span><strong>{result.error?'Unavailable':!result.data?'…':format(value,metric.unit)}</strong><small>{result.error?<button onClick={result.retry}>Retry</button>:delta===null?'Selected dataset · filtered view':`${delta>=0?'↑':'↓'} ${Math.abs(delta*100).toFixed(1)}% vs previous period`}</small><details><summary aria-label={'Definition of '+metric.label}>ⓘ Definition</summary><p>{metric.definition}. {request.period?.field.replaceAll('_',' ')||'All dates'}.</p></details></article>;
}

import {useEffect,useRef,useState} from 'react';
import type {ChartSpec} from './pageTypes';
import type {QueryResponse} from './types';
const COLORS=['#426cce','#37a89b','#8b79c4','#e6ae51','#7695b9','#d37b84'];
export function Chart({data,spec,onInspect}:{data:QueryResponse;spec:ChartSpec;onInspect:(key:string|string[])=>void}){
 const ref=useRef<HTMLDivElement>(null);const [error,setError]=useState(false);
 useEffect(()=>{
  const el=ref.current;if(!el)return;let disposed=false;let plot:any;let resize:ResizeObserver|undefined;
  import('plotly.js-basic-dist-min').then(async({default:P})=>{
   if(disposed)return;plot=P;
   const groups=data.groups;const labels=groups.map(g=>Array.isArray(g.key)?g.key[0]:g.key);const values=groups.map(g=>g.values[spec.metric]===null?null:Number(g.values[spec.metric]));
   let traces:any[]=[];
   if(spec.kind==='donut')traces=[{type:'pie',labels,values,hole:.68,textinfo:'none',marker:{colors:COLORS},customdata:groups.map(g=>g.key)}];
   else if(spec.kind==='stacked'){
    const series=[...new Set(groups.map(g=>(g.key as string[])[1]))];
    traces=series.map((s,i)=>{const gs=groups.filter(g=>(g.key as string[])[1]===s);return {type:'bar',name:s,x:gs.map(g=>g.key[0]),y:gs.map(g=>Number(g.values[spec.metric])),marker:{color:COLORS[i%COLORS.length]},customdata:gs.map(g=>g.key)}});
   }else if(spec.kind==='bubble')traces=[{type:'scatter',mode:'markers',x:groups.map(g=>g.key[0]),y:groups.map(g=>g.key[1]),marker:{size:values.map(v=>Math.max(7,Math.sqrt(v||0)*4)),color:COLORS[1],opacity:.7},text:values.map(String),customdata:groups.map(g=>g.key),hovertemplate:'%{x} · %{y}: %{text}<extra></extra>'}];
   else traces=[{type:spec.kind==='bar'?'bar':'scatter',mode:spec.kind==='line'?'lines+markers':'markers',x:labels,y:values,line:{color:COLORS[0],width:2.5,shape:'spline'},marker:{color:COLORS[0],size:spec.kind==='scatter'?10:4},fill:spec.kind==='line'?'tozeroy':undefined,fillcolor:'rgba(66,108,206,.07)',customdata:groups.map(g=>g.key)}];
   await P.newPlot(el,traces,{autosize:true,height:270,margin:{l:52,r:18,t:12,b:62},paper_bgcolor:'transparent',plot_bgcolor:'transparent',font:{family:'Inter, system-ui, sans-serif',size:11,color:'#61728a'},showlegend:['donut','stacked'].includes(spec.kind),legend:{orientation:'h',y:-.25},barmode:'stack',xaxis:{showgrid:false,automargin:true},yaxis:{gridcolor:'#edf1f6',zeroline:false,automargin:true,tickformat:['conversion','win_rate'].includes(spec.metric)?'.0%':undefined}},{displayModeBar:false,responsive:true});
   if(disposed){P.purge(el);return;}
   (el as any).on('plotly_click',(e:any)=>{const key=e.points?.[0]?.customdata;if(key!==undefined)onInspect(key)});
   resize=new ResizeObserver(()=>{if(!disposed)P.Plots.resize(el)});resize.observe(el);
  }).catch(()=>{if(!disposed)setError(true)});
  return()=>{disposed=true;resize?.disconnect();if(plot)plot.purge(el)};
 },[data,spec.metric,spec.kind]);
 return error?<p role="alert">Chart could not load. Use the data table below.</p>:<div ref={ref} className="plot" aria-label={spec.title+' visualization'}/>;
}

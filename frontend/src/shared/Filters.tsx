import {useState} from 'react';
import type {Filters as Values} from './types';
const labels:Record<string,string>={account:'Account',account_type:'Account type',industry:'Industry',type:'Type / reason',division:'Region / division',owner:'Owner',priority:'Priority',days_bucket:'Days to close'};
function Filter({name,options,selected,onChange}:{name:string;options:string[];selected:string[];onChange:(v:string[])=>void}){
 const [search,setSearch]=useState('');
 return <div className="filter"><span>{name}</span><details className="filter-menu" onKeyDown={e=>{if(e.key==='Escape'){e.currentTarget.open=false;e.currentTarget.querySelector('summary')?.focus()}}}><summary role="button" aria-label={name+' filter'}>{selected.length?`${selected[0]}${selected.length>1?` +${selected.length-1}`:''}`:`All ${name.toLowerCase()}`}<span>⌄</span></summary><div className="filter-popover">{options.length>10&&<input aria-label={'Search '+name} placeholder="Search options…" value={search} onChange={e=>setSearch(e.target.value)}/>}<button className="text-button" onClick={()=>onChange([])}>Clear selection</button><div className="filter-options">{options.filter(v=>v.toLowerCase().includes(search.toLowerCase())).map(v=><label key={v}><input type="checkbox" checked={selected.includes(v)} onChange={e=>onChange(e.target.checked?[...selected,v]:selected.filter(x=>x!==v))}/>{v}</label>)}</div></div></details></div>;
}
export function Filters({keys,options,values,onChange,onReset}:{keys:string[];options:Record<string,string[]>;values:Values;onChange:(key:string,values:string[])=>void;onReset:()=>void}){
 return <div className="filter-strip">{keys.map(k=><Filter key={k} name={labels[k]||k} options={options[k]||[]} selected={values[k]||[]} onChange={v=>onChange(k,v)}/>)}<button className="text-button" onClick={onReset}>Reset filters</button></div>;
}

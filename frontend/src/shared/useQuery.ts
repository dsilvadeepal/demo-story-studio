import {useEffect,useState} from 'react';
import {fetchQuery} from './api';
import type {QueryRequest,QueryResponse} from './types';
export function useQuery(req:QueryRequest){
 const key=JSON.stringify(req);const [attempt,setAttempt]=useState(0);
 const [state,setState]=useState<{key:string;data?:QueryResponse;error?:string}>({key});
 useEffect(()=>{const controller=new AbortController();let current=true;setState({key});fetchQuery(req,controller.signal).then(data=>{if(current)setState({key,data})}).catch(e=>{if(current&&e.name!=='AbortError')setState({key,error:e.message})});return()=>{current=false;controller.abort()};},[key,attempt]);
 return {...(state.key===key?state:{key}),retry:()=>setAttempt(x=>x+1)};
}

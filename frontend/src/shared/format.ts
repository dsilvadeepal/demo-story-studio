export function format(v:string|number|null|undefined,unit='count'){
 if(v===null||v===undefined)return '—';const n=Number(v);
 if(unit==='currency')return new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:0,notation:Math.abs(n)>=1e6?'compact':'standard'}).format(n);
 if(unit==='percent')return (n*100).toFixed(1)+'%';
 if(unit==='days')return n.toFixed(1)+' days';
 return new Intl.NumberFormat('en-US',{maximumFractionDigits:1}).format(n);
}

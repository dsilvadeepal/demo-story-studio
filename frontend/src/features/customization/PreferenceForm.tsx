import {useState} from 'react';
type Props={busy:boolean;audience:string;intent:string;onAudience:(value:string)=>void;onIntent:(value:string)=>void;onSave:(text:string)=>Promise<boolean>};
export function PreferenceForm({busy,audience,intent,onAudience,onIntent,onSave}:Props){
 const [text,setText]=useState(''),[saving,setSaving]=useState(false),[saved,setSaved]=useState(false);
 return <form className="memory-card" onSubmit={async e=>{e.preventDefault();if(saving||busy||text.trim().length<10)return;setSaving(true);setSaved(false);try{if(await onSave(text.trim())){setText('');setSaved(true)}}finally{setSaving(false)}}}>
  <h3>Add a preference</h3>
  <label>Preference<textarea value={text} maxLength={600} rows={3} disabled={saving} onChange={e=>{setText(e.target.value);setSaved(false)}} placeholder="Example: Use customer-friendly terms in HVAC demos."/></label>
  <details><summary>When to use this</summary><p>Applies to new conversations with this audience and purpose.</p><label>Audience<input value={audience} maxLength={80} disabled={saving} onChange={e=>onAudience(e.target.value)}/></label><label>Demo purpose<input value={intent} maxLength={120} disabled={saving} onChange={e=>onIntent(e.target.value)}/></label></details>
  <p>Save this wording to Mem0 for future demos.</p>
  <button className="primary" type="submit" disabled={busy||saving||text.trim().length<10}>{saving?'Saving…':'Save preference'}</button>
  {saved&&<p role="status">Saved for future demos.</p>}
 </form>;
}

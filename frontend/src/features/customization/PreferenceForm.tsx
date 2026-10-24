import {useState} from 'react';
type Props={busy:boolean;audience:string;intent:string;onAudience:(value:string)=>void;onIntent:(value:string)=>void;onSave:(text:string)=>Promise<boolean>};
export function PreferenceForm({busy,audience,intent,onAudience,onIntent,onSave}:Props){
 const [text,setText]=useState(''),[saving,setSaving]=useState(false),[saved,setSaved]=useState(false);
 return <form className="memory-card" onSubmit={async e=>{e.preventDefault();if(saving||busy||text.trim().length<10)return;setSaving(true);setSaved(false);try{if(await onSave(text.trim())){setText('');setSaved(true)}}finally{setSaving(false)}}}>
  <h3>Remember for future demos</h3>
  <label>Preference<textarea value={text} maxLength={600} rows={3} disabled={saving} onChange={e=>{setText(e.target.value);setSaved(false)}} placeholder="For HVAC demos, use customer-friendly HVAC terminology instead of internal technical codes."/></label>
  <details><summary>Optional context</summary><label>Audience<input value={audience} maxLength={80} disabled={saving} onChange={e=>onAudience(e.target.value)}/></label><label>Demo purpose<input value={intent} maxLength={120} disabled={saving} onChange={e=>onIntent(e.target.value)}/></label></details>
  <p>Save confirms this wording and stores it in Mem0 for matching future demos. Your current preview stays unchanged.</p>
  <button className="primary" type="submit" disabled={busy||saving||text.trim().length<10}>{saving?'Saving…':'Save preference'}</button>
  {saved&&<p role="status">Saved. Start a new customization with the same audience and purpose; look for “Used in this conversation” to confirm it was retrieved.</p>}
 </form>;
}

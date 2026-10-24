import {useEffect,useRef} from 'react';
export function RecoveryDialog({revision,onConfirm,onCancel,busy}:{revision:number;onConfirm:()=>void;onCancel:()=>void;busy:boolean}){
 const dialog=useRef<HTMLDialogElement>(null);
 useEffect(()=>{const before=document.activeElement as HTMLElement;dialog.current?.showModal();return()=>{dialog.current?.close();before?.focus()}},[]);
 return <dialog ref={dialog} className="brief-dialog" onCancel={onCancel}><h2>Restore revision {revision}?</h2><p>This makes the selected saved revision current across Sales and Service. The previous revision remains in history.</p><footer><button disabled={busy} onClick={onCancel}>Cancel restoration</button><button className="primary" disabled={busy} onClick={onConfirm}>Confirm restoration</button></footer></dialog>;
}

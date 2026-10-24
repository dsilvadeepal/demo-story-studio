import {useEffect,useRef,type ReactNode} from 'react';
export function ReviewDrawer({open,onClose,revision,children}:{open:boolean;onClose:()=>void;revision:number;children:ReactNode}){
 const ref=useRef<HTMLDialogElement>(null);
 useEffect(()=>{const dialog=ref.current;if(!dialog)return;if(open){const before=document.activeElement as HTMLElement;if(!dialog.open){if(dialog.showModal)dialog.showModal();else dialog.setAttribute('open','')}dialog.querySelector('textarea')?.focus();return()=>{if(dialog.open)dialog.close?.();before?.focus()}}else if(dialog.open)dialog.close?.()},[open]);
 useEffect(()=>{ref.current?.querySelector('.review-scroll')?.scrollTo?.(0,0)},[revision]);
 return <dialog ref={ref} className="review-drawer" aria-label={`Review preview revision ${revision}`} onCancel={e=>{e.preventDefault();onClose()}}><header className="drawer-header"><div><span className="eyebrow">HUMAN REVIEW</span><h2>Refine revision {revision}</h2></div><button onClick={onClose} aria-label="Close review">×</button></header>{children}<button className="drawer-dashboard" onClick={onClose}>Back to preview</button></dialog>;
}

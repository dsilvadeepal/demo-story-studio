import {it,expect,vi} from 'vitest';
import {render,screen,fireEvent} from '@testing-library/react';
import {RevisionHistory} from './RevisionHistory';
it('offers reversible cleanup and hides archived revisions by default',()=>{
 const cleanup=vi.fn(),restore=vi.fn();
 const items=Array.from({length:5},(_,i)=>({id:String(i),parent_id:null,revision:i+1,content_hash:'hash',as_of_date:'2026-10-21',status:'preview' as const,archived:i===0}));
 render(<RevisionHistory items={items} activeId="4" busy={false} onSelect={vi.fn()} onRecover={vi.fn()} onCleanup={cleanup} onRestoreHistory={restore}/>);
 fireEvent.click(screen.getByText('Revision history (4/20)'));
 expect(screen.queryByText('Revision 1 · preview · Archived')).toBeNull();
 fireEvent.click(screen.getByRole('button',{name:'Clean up old previews'}));expect(cleanup).toHaveBeenCalledOnce();
 fireEvent.click(screen.getByLabelText('Show archived (1)'));
 fireEvent.click(screen.getByRole('button',{name:'Return revision 1 to history'}));expect(restore).toHaveBeenCalledWith('0');
});

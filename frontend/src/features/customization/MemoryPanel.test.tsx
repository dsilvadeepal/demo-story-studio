import {it,expect,vi,afterEach} from 'vitest';
import {render,screen,fireEvent,cleanup} from '@testing-library/react';
import {MemoryPanel} from './MemoryPanel';
afterEach(cleanup);
const item={id:'memory',provider_id:null,content_hash:'exact',correlation:'correlation',status:'proposed',draft:{kind:'preference',text:'Focus on larger open deals for leadership demos.',scope:{owner_id:'owner',workspace_id:'local',domain:'sales',audience:'leadership',intent:'quarterly review'},source_run_id:'run',source_revision_id:null}};
it('displays exact wording and scope before confirming; unknown deletion is not success',()=>{
 const confirm=vi.fn(),forget=vi.fn();
 const props={items:[item],usedIds:[],onConfirm:confirm,onIgnore:vi.fn(),onUpdate:vi.fn(),onForget:forget,busy:false};
 const view=render(<MemoryPanel {...props}/>);
 expect(screen.getByText(item.draft.text,{selector:'blockquote'})).toBeTruthy();expect(screen.getByText(/leadership.*quarterly review/)).toBeTruthy();expect(confirm).not.toHaveBeenCalled();
 fireEvent.click(screen.getByRole('button',{name:'Confirm exact text and save'}));expect(confirm).toHaveBeenCalledWith(item);
 view.rerender(<MemoryPanel {...props} items={[{...item,status:'deletion-pending'}]}/>);
 expect(screen.getByText(/Deletion pending/)).toBeTruthy();expect(screen.queryByText('Deleted')).toBeNull();
});
it('marks used memory and separates ignore and proposed updates from saving',()=>{
 const update=vi.fn(),ignore=vi.fn(),confirm=vi.fn();
 render(<MemoryPanel items={[{...item,status:'saved'}]} usedIds={['memory']} onConfirm={confirm} onIgnore={ignore} onUpdate={update} onForget={vi.fn()} busy={false}/>);
 expect(screen.getByText('Used in this conversation')).toBeTruthy();
 fireEvent.click(screen.getByRole('button',{name:'Ignore for this conversation'}));expect(ignore).toHaveBeenCalledWith('memory');
 fireEvent.change(screen.getByLabelText('Edit reusable guidance'),{target:{value:'Focus on open opportunities for leadership demos.'}});
 fireEvent.click(screen.getByRole('button',{name:'Propose updated wording'}));expect(update).toHaveBeenCalled();expect(confirm).not.toHaveBeenCalled();
});

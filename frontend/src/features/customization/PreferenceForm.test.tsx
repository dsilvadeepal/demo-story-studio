import {render,screen,fireEvent,waitFor,cleanup} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {PreferenceForm} from './PreferenceForm';
afterEach(cleanup);
const text='For HVAC demos, use customer-friendly terminology.';
const props={busy:false,audience:'general',intent:'demo preparation',onAudience:vi.fn(),onIntent:vi.fn()};
it('requires explicit save and shows success only after verified completion',async()=>{
 let finish!:(value:boolean)=>void;const save=vi.fn(()=>new Promise<boolean>(resolve=>{finish=resolve}));
 render(<PreferenceForm {...props} onSave={save}/>);
 fireEvent.change(screen.getByLabelText('Remember for next time'),{target:{value:text}});expect(save).not.toHaveBeenCalled();
 fireEvent.click(screen.getByRole('button',{name:'Save preference'}));expect(save).toHaveBeenCalledWith(text);
 expect(screen.queryByRole('status')).toBeNull();expect((screen.getByRole('button',{name:'Saving…'}) as HTMLButtonElement).disabled).toBe(true);
 finish(true);await waitFor(()=>expect(screen.getByRole('status').textContent).toContain('Saved for future demos.'));
 expect((screen.getByLabelText('Remember for next time') as HTMLTextAreaElement).value).toBe('');
});
it('retains wording and does not claim success on an unverified save',async()=>{
 render(<PreferenceForm {...props} onSave={vi.fn().mockResolvedValue(false)}/>);
 fireEvent.change(screen.getByLabelText('Remember for next time'),{target:{value:text}});fireEvent.click(screen.getByRole('button',{name:'Save preference'}));
 await waitFor(()=>expect(screen.getByRole('button',{name:'Save preference'})).toBeTruthy());
 expect(screen.queryByRole('status')).toBeNull();expect((screen.getByLabelText('Remember for next time') as HTMLTextAreaElement).value).toBe(text);
});

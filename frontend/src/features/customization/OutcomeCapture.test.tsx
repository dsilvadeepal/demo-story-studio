import {it,expect,vi,afterEach} from 'vitest';
import {render,screen,fireEvent,cleanup,waitFor} from '@testing-library/react';
import {OutcomeCapture} from './OutcomeCapture';
afterEach(cleanup);
it('requires an affirmative outcome and separate draft action after Apply',async()=>{
 const outcome=vi.fn().mockResolvedValue(undefined),propose=vi.fn().mockResolvedValue(undefined);
 render(<OutcomeCapture onOutcome={outcome} onPropose={propose} busy={false}/>);
 expect(propose).not.toHaveBeenCalled();expect(screen.queryByLabelText('Reusable recipe wording')).toBeNull();
 fireEvent.click(screen.getByRole('button',{name:'Yes, this worked'}));
 await waitFor(()=>expect(screen.getByLabelText('Reusable recipe wording')).toBeTruthy());
 expect(outcome).toHaveBeenCalledWith(true);expect(propose).not.toHaveBeenCalled();
 fireEvent.change(screen.getByLabelText('Reusable recipe wording'),{target:{value:'Focus on selected larger open deals for leadership demos.'}});
 fireEvent.click(screen.getByRole('button',{name:'Create recipe draft for review'}));expect(propose).toHaveBeenCalledOnce();
});

it('shows failed outcome persistence without unlocking a recipe',async()=>{
 render(<OutcomeCapture onOutcome={vi.fn().mockRejectedValue(new Error('Unavailable'))} onPropose={vi.fn()} busy={false}/>);
 fireEvent.click(screen.getByRole('button',{name:'Yes, this worked'}));
 await waitFor(()=>expect(screen.getByRole('alert').textContent).toContain('Could not record'));
 expect(screen.queryByLabelText('Reusable recipe wording')).toBeNull();
});

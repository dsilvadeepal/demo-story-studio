import {it,expect,vi} from 'vitest';
import {render,screen,fireEvent,cleanup} from '@testing-library/react';
import {Filters} from './Filters';
it('supports multiple filter selections without losing the first',()=>{
 const onChange=vi.fn();render(<Filters keys={['industry']} options={{industry:['Technology','Healthcare']}} values={{industry:['Technology']}} onChange={onChange} onReset={()=>{}}/>);
 fireEvent.click(screen.getByRole('button',{name:'Industry filter'}));
 const checkbox=screen.getByRole('checkbox',{name:'Healthcare'});fireEvent.click(checkbox);
 expect(onChange).toHaveBeenCalledWith('industry',['Technology','Healthcare']);cleanup();
});

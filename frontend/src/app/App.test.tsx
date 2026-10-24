import {it,expect} from 'vitest';
import {render,screen,cleanup} from '@testing-library/react';
import {Studio} from './Studio';
it('offers only Sales and Service as starting choices',()=>{
 render(<Studio onChoose={()=>{}}/>);
 expect(screen.getByRole('button',{name:/Open Sales/})).toBeTruthy();
 expect(screen.getByRole('button',{name:/Open Service/})).toBeTruthy();
 expect(screen.queryByText('Retail')).toBeNull();
 expect(screen.queryByRole('button',{name:/Generate/})).toBeNull();cleanup();
});

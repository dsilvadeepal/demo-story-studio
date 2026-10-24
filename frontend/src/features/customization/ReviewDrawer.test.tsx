import {it,expect,vi,afterEach} from 'vitest';
import {render,screen,fireEvent,cleanup} from '@testing-library/react';
import {ReviewDrawer} from './ReviewDrawer';
afterEach(cleanup);
it('supports Escape and an explicit close without activation',()=>{
 HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','')};HTMLDialogElement.prototype.close=function(){this.removeAttribute('open')};
 const close=vi.fn();const view=render(<ReviewDrawer open onClose={close} revision={7}><p>Review evidence</p></ReviewDrawer>);
 fireEvent(screen.getByRole('dialog'),new Event('cancel',{cancelable:true}));expect(close).toHaveBeenCalledOnce();
 fireEvent.click(screen.getByRole('button',{name:'Back to preview'}));expect(close).toHaveBeenCalledTimes(2);
 view.rerender(<ReviewDrawer open={false} onClose={close} revision={7}><p>Review evidence</p></ReviewDrawer>);
 expect(screen.queryByRole('dialog')).toBeNull();
});

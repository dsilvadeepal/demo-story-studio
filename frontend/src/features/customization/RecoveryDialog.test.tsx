import {it,expect,vi,afterEach} from 'vitest';
import {render,screen,fireEvent,cleanup} from '@testing-library/react';
import {RecoveryDialog} from './RecoveryDialog';
afterEach(cleanup);
it('requires an explicit in-page confirmation and supports cancellation',()=>{
 HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','')};
 HTMLDialogElement.prototype.close=function(){this.removeAttribute('open')};
 const confirm=vi.fn(),cancel=vi.fn();
 render(<RecoveryDialog revision={1} onConfirm={confirm} onCancel={cancel} busy={false}/>);
 expect(confirm).not.toHaveBeenCalled();
 fireEvent.click(screen.getByRole('button',{name:'Cancel restoration'}));expect(cancel).toHaveBeenCalledOnce();
 fireEvent.click(screen.getByRole('button',{name:'Confirm restoration'}));expect(confirm).toHaveBeenCalledOnce();
});

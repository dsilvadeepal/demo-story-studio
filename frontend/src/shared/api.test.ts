import {it,expect,vi} from 'vitest';
import {api} from './api';
it('explains stale two-tab approvals without suggesting that data changed',async()=>{
 const original=globalThis.fetch;
 globalThis.fetch=vi.fn().mockResolvedValue({ok:false,status:409,json:async()=>({detail:'STALE_ACTIVE'})});
 try{await expect(api('/v1/scenarios/apply',{})).rejects.toThrow('stale. Reload the current dataset and review again.')}finally{globalThis.fetch=original}
});

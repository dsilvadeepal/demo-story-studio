from sqlalchemy import select
from ..db import tables
from .analytics import read_facts,filtered,context,serialize,dataset

def list_records(c,req):
    if (req.entity=='opportunities') != (req.dashboard=='sales'): raise ValueError('Entity and dashboard mismatch')
    # Record evidence is always at fact grain, regardless of the chart's dimension.
    base=req.model_copy(update={'dimension':None}); rows,ds=read_facts(c,base); rows=filtered(rows,base)
    allowed=['name','amount','created_at','close_date','id'] if req.entity=='opportunities' else ['created_at','priority','status','id']
    if req.sort not in allowed: raise ValueError('Unsupported entity sort')
    rows.sort(key=lambda r:(r[req.sort],r['id']),reverse=req.descending)
    selected=rows[req.cursor:req.cursor+req.page_size]; end=req.cursor+len(selected)
    out=context(req,ds); out.update(rows=selected,total=len(rows),next_cursor=end if end<len(rows) else None)
    return serialize(out)

def get_record(c,dataset_id,entity,id):
    dataset(c,dataset_id)
    if entity not in ['opportunities','cases']: raise ValueError('Unsupported entity')
    def get(table,key):
        if key is None:return None
        t=tables[table]; r=c.execute(select(t).where(t.c.dataset_id==dataset_id,t.c.id==key)).mappings().first()
        return dict(r) if r else None
    r=get(entity,id)
    if not r: raise LookupError('Record not found')
    out={'record':r,'account':get('accounts',r['account_id']),'owner':get('users',r['owner_id'])}
    ct=tables['contacts']; out['contacts']=[dict(x) for x in c.execute(select(ct).where(ct.c.dataset_id==dataset_id,ct.c.account_id==r['account_id'])).mappings()] if r['account_id'] else []
    if entity=='opportunities':
        l=tables['opportunity_line_items']; out['lines']=[]
        for line in c.execute(select(l).where(l.c.dataset_id==dataset_id,l.c.opportunity_id==id)).mappings():
            entry=get('pricebook_entries',line['pricebook_entry_id']); out['lines'].append(dict(line,product=get('products',entry['product_id']),pricebook=get('pricebooks',entry['pricebook_id']),list_price=entry['unit_price']))
    else: out['contact']=get('contacts',r['contact_id'])
    return serialize(out)

"""Offline deterministic data; no source record ingestion."""
import argparse, calendar, hashlib, json, random
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal
from sqlalchemy import select
from .db import engine, manifest, tables
AS_OF=date(2026,10,21)
COUNTS=dict(accounts=120,contacts=240,users=24,products=80,pricebooks=2,pricebook_entries=160,opportunities=1200,opportunity_line_items=3600,cases=2400)
STAGES=['Prospecting','Qualification','Needs Analysis','Value Proposition','Id. Decision Makers','Perception Analysis','Proposal/Price Quote','Negotiation/Review','Closed Won','Closed Lost']
FAMILIES=['Office','Technology','Furniture','Facilities','Safety','Packaging','Kitchen','Cleaning']
INDUSTRIES=['Technology','Healthcare','Manufacturing','Education','Professional Services','Hospitality']
def ident(name,i): return f'{name}-{i:04d}'
def checksum(rows): return hashlib.sha256(json.dumps(sorted(rows,key=lambda r:r['id']),sort_keys=True,default=lambda v: format(v.normalize(),'f') if isinstance(v,Decimal) else str(v),separators=(',',':')).encode()).hexdigest()
def generate(seed:int=42,as_of:date=AS_OF):
    rng=random.Random(seed); ds=f'baseline-v1-{seed}-{as_of}'; ts={k:[] for k in COUNTS}; now=datetime.combine(as_of,datetime.min.time(),timezone.utc)
    def add(table,i,**values): ts[table].append(dict(dataset_id=ds,id=ident(table,i),**values))
    for i in range(120): add('accounts',i,name=f'{["Cedar","Summit","Harbor","Juniper","Northstar","Meadow"][i%6]} { ["Works","Labs","Group","Partners","Systems"][i%5]} {i+1}',type=['Enterprise','Mid-market','Small Business'][i%3],industry=INDUSTRIES[i%6])
    for i in range(24): add('users',i,first_name=['Alex','Morgan','Sam','Jordan','Taylor','Riley'][i%6],last_name=f'{["Chen","Patel","Reed","Brooks"][i//6]}',department='Sales' if i<12 else 'Service',division=['East','West','Central'][i%3])
    for i in range(240): add('contacts',i,account_id=ident('accounts',i//2),first_name=f'Contact {i+1}',last_name='Demo',title=['Operations Lead','Procurement Manager'][i%2])
    for i in range(80): add('products',i,name=f'{FAMILIES[i%8]} collection {i//8+1}',code=f'SKU-{i:04}',family=FAMILIES[i%8])
    for i in range(2): add('pricebooks',i,name=['Standard','Enterprise'][i],description='Synthetic USD pricebook')
    for i in range(160): add('pricebook_entries',i,product_id=ident('products',i%80),pricebook_id=ident('pricebooks',i//80),unit_price=Decimal((i%80+1)*25)*(Decimal('1') if i<80 else Decimal('.9')))
    for i in range(1200):
        age=rng.randint(1,730); created=max(now-timedelta(days=730),now-timedelta(days=age,hours=rng.randint(0,23))); stage=STAGES[i%10]
        closed=stage.startswith('Closed'); close=created+timedelta(days=rng.randint(1,min(age,120))) if closed else now+timedelta(days=rng.randint(-25,240))
        close=max(close,created)
        add('opportunities',i,name=f'{FAMILIES[i%8]} renewal {i+1}',account_id=ident('accounts',rng.randrange(114)),owner_id=ident('users',rng.choices(range(12),weights=range(1,13))[0]),type=['New Business','Expansion','Renewal'][i%3],stage=stage,probability=Decimal(100 if stage=='Closed Won' else 0 if closed else (i%8+1)*10),created_at=created,close_date=close)
        for j in range(3):
            e=rng.randrange(152); price=ts['pricebook_entries'][e]['unit_price']; seasonal=2 if created.month in (9,10,11) else 1
            add('opportunity_line_items',i*3+j,opportunity_id=ident('opportunities',i),pricebook_entry_id=ident('pricebook_entries',e),unit_price=(price*Decimal(rng.choice(['1','.95','.9','.85']))).quantize(Decimal('.01')),quantity=Decimal(rng.randint(2,50)*seasonal))
    for i in range(2400):
        age=rng.randint(1,730); created=max(now-timedelta(days=730),now-timedelta(days=age,hours=rng.randint(0,23))); closed=rng.random()<.7; account=None if i<120 else rng.randrange(114)
        add('cases',i,subject=f'{["Setup assistance","Delivery question","Product guidance","Replacement request"][i%4]} #{i+1}',account_id=None if account is None else ident('accounts',account),contact_id=None if account is None else ident('contacts',account*2+i%2),owner_id=ident('users',12+rng.choices(range(12),weights=range(12,0,-1))[0]),priority=['Critical','High','Medium','Low'][i%4],status='Closed' if closed else 'Working' if rng.random()<.7 else 'New',type=['Technical','Order','Product','Billing','Returns'][i%5],origin=['Email','Phone','Web','Chat'][rng.randrange(4)],created_at=created,closed_date=created+timedelta(days=rng.randint(1,min(age,15))) if closed else None)
    m=dict(id=ds,revision=1,semantic_version='1.0.0',as_of_date=as_of,seed=seed,generator_version=1,counts={k:len(v) for k,v in ts.items()},checksums={k:checksum(v) for k,v in ts.items()},presentation={})
    return {'manifest':m,'tables':ts}
def load_baseline(connection,bundle):
    m=bundle['manifest']; old=connection.execute(select(manifest).where(manifest.c.id==m['id'])).mappings().first()
    if old:
        if old['checksums']!=m['checksums']: raise ValueError('Dataset ID already exists with different content')
        for name,t in tables.items():
            rows=[dict(r) for r in connection.execute(select(t).where(t.c.dataset_id==m['id'])).mappings()]
            if checksum(rows)!=m['checksums'][name]: raise ValueError('Existing stored records differ from the immutable baseline')
        return dict(old)
    connection.execute(manifest.insert(),m)
    for table in ['accounts','users','contacts','products','pricebooks','pricebook_entries','opportunities','opportunity_line_items','cases']: connection.execute(tables[table].insert(),bundle['tables'][table])
    return m
if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--seed',type=int,default=42); p.add_argument('--as-of',type=date.fromisoformat,default=AS_OF); a=p.parse_args()
    with engine(admin=True).begin() as c: m=load_baseline(c,generate(a.seed,a.as_of))
    print(json.dumps({'dataset':m['id'],'counts':m['counts']},indent=2))

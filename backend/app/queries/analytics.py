"""SQL fact preaggregation and exact Decimal analytics over a bounded baseline."""
from collections import defaultdict
from datetime import date,timedelta
from decimal import Decimal as D
import hashlib,json
from sqlalchemy import select,func,literal
from ..db import tables,manifest
from ..catalog import SALES,SERVICE,FILTERS,DIMENSIONS
from ..seed import STAGES
MAX_FACTS=20000

def dataset(c,id):
    row=c.execute(select(manifest).where(manifest.c.id==id)).mappings().first()
    if not row: raise LookupError('Dataset not found')
    return dict(row)
def days_bucket(n): return 'Overdue' if n<0 else '0–30 days' if n<30 else '1–3 months' if n<90 else '3–6 months' if n<180 else '>6 months'
def read_facts(c,req):
    ds=dataset(c,req.dataset_id); a=tables['accounts']; u=tables['users']; name=(u.c.first_name+literal(' ')+u.c.last_name).label('owner')
    if req.dashboard=='sales':
        o=tables['opportunities']; l=tables['opportunity_line_items']; e=tables['pricebook_entries']; p=tables['products']
        money=select(l.c.dataset_id,l.c.opportunity_id,func.sum(l.c.quantity*l.c.unit_price).label('amount'))
        if req.dimension in ['product','family']:
            dim=p.c.name if req.dimension=='product' else p.c.family
            money=money.add_columns(dim.label('product_dimension')).select_from(l.join(e,(l.c.dataset_id==e.c.dataset_id)&(l.c.pricebook_entry_id==e.c.id)).join(p,(e.c.dataset_id==p.c.dataset_id)&(e.c.product_id==p.c.id))).group_by(dim)
        money=money.where(l.c.dataset_id==req.dataset_id).group_by(l.c.dataset_id,l.c.opportunity_id).subquery()
        join=o.join(a,(o.c.dataset_id==a.c.dataset_id)&(o.c.account_id==a.c.id)).join(u,(o.c.dataset_id==u.c.dataset_id)&(o.c.owner_id==u.c.id)).join(money,(o.c.dataset_id==money.c.dataset_id)&(o.c.id==money.c.opportunity_id))
        q=select(o,a.c.name.label('account'),a.c.type.label('account_type'),a.c.industry,name,money.c.amount).select_from(join).where(o.c.dataset_id==req.dataset_id)
        if req.dimension in ['product','family']: q=q.add_columns(money.c.product_dimension)
    else:
        t=tables['cases']; join=t.outerjoin(a,(t.c.dataset_id==a.c.dataset_id)&(t.c.account_id==a.c.id)).join(u,(t.c.dataset_id==u.c.dataset_id)&(t.c.owner_id==u.c.id))
        q=select(t,a.c.name.label('account'),a.c.industry,name,u.c.division).select_from(join).where(t.c.dataset_id==req.dataset_id)
    rows=[dict(r) for r in c.execute(q.limit(MAX_FACTS+1)).mappings()]
    if len(rows)>MAX_FACTS: raise ValueError('Dataset exceeds foundation fact limit; narrow at the query service before increasing capacity')
    for r in rows:
        r['account']=r['account'] or 'Unassigned account'; r['industry']=r['industry'] or 'Unassigned account'
        if req.dashboard=='sales': r['days_bucket']=days_bucket((r['close_date'].date()-ds['as_of_date']).days)
    return rows,ds

def filtered(rows,req,period=True):
    for key,values in req.filters.items():
        if key not in [*FILTERS[req.dashboard],'id']: raise ValueError(f'Unsupported filter: {key}')
        if len(values)>(MAX_FACTS if key=='id' else 200): raise ValueError('Too many filter selections')
        options={r[key] for r in rows}
        if any(v not in options for v in values): raise ValueError(f'Unknown option for {key}')
    result=[r for r in rows if all((not vs and k!='id') or str(r[k]) in vs for k,vs in req.filters.items())]
    if period and req.period:
        field=req.period.field
        if field not in (['created_at','close_date'] if req.dashboard=='sales' else ['created_at','closed_date']): raise ValueError('Unsupported period field')
        result=[r for r in result if r[field] is not None and req.period.start<=r[field].date()<=req.period.end]
    return result

def summarize(rows,domain,as_of):
    def ratio(a,b): return D(a)/D(b) if b else None
    if domain=='sales':
        won=[r for r in rows if 'WON' in r['stage'].upper()]; closed=[r for r in rows if 'CLOSED' in r['stage'].upper()]; opened=[r for r in rows if 'CLOSED' not in r['stage'].upper()]
        amount=lambda rs:sum((r['amount'] for r in rs),D(0)); ids=lambda rs:len({r['id'] for r in rs})
        # One duration per opportunity even in product-grain input.
        unique_won={r['id']:r for r in won}.values()
        duration=sum((D(str((r['close_date']-r['created_at']).total_seconds()))/D(86400) for r in unique_won),D(0))
        return dict(total_sales=amount(won),win_rate=ratio(ids(won),ids(rows)),conversion=ratio(amount(won),amount(closed)),average_won_deal=ratio(amount(won),ids(won)),won_cycle=ratio(duration,ids(won)),pipeline_generated=amount(rows),open_opportunities=ids(opened),weighted_pipeline=sum((r['amount']*r['probability']/100 for r in opened),D(0)))
    closed=[r for r in rows if r['closed_date'] is not None]
    return dict(created_cases=len(rows),closed_cases=len(closed),close_days=ratio(sum((r['closed_date'].date()-r['created_at'].date()).days for r in closed),len(closed)),open_cases=len(rows)-len(closed),missing_accounts=sum(r.get('account') in [None,'Unassigned account'] for r in rows))

def context(req,ds):
    canonical=req.model_dump(mode='json'); digest=hashlib.sha256(json.dumps(canonical,sort_keys=True).encode()).hexdigest()[:16]
    return dict(dataset_id=ds['id'],revision=ds['revision'],semantic_version=ds['semantic_version'],as_of_date=str(ds['as_of_date']),effective_filters=req.filters,period=canonical.get('period'),query_id=digest,warnings=[])
def serialize(v):
    if isinstance(v,D): return format(v,'f')
    if isinstance(v,(date,)): return v.isoformat()
    if isinstance(v,dict): return {k:serialize(x) for k,x in v.items()}
    if isinstance(v,list): return [serialize(x) for x in v]
    return v

def query(c,req):
    metrics=SALES if req.dashboard=='sales' else SERVICE
    ids=req.metric_ids or list(metrics)
    if set(ids)-set(metrics): raise ValueError('Unsupported metric')
    if req.dimension and req.dimension not in DIMENSIONS[req.dashboard]: raise ValueError('Unsupported dimension')
    allrows,ds=read_facts(c,req); rows=filtered(allrows,req)
    def select_metrics(rs): return {k:v for k,v in summarize(rs,req.dashboard,ds['as_of_date']).items() if k in ids}
    groups=defaultdict(list)
    for r in rows:
        dim=req.dimension
        if not dim: break
        if dim=='month': key=r[(req.period.field if req.period else 'created_at')].strftime('%Y-%m')
        elif dim=='week_origin': key=((r['created_at'].date()-timedelta(days=r['created_at'].weekday())).isoformat(),r['origin'])
        elif dim=='type_division': key=(r['type'],r['division'])
        elif dim in ['product','family']: key=r['product_dimension']
        elif dim=='close_date': key=(r['close_date'].date().isoformat(),r['id'])
        else: key=r[dim]
        groups[key].append(r)
    def order(key):
        if req.dimension=='stage': return STAGES.index(key) if key in STAGES else 99
        if req.dimension=='days_bucket': return ['Overdue','0–30 days','1–3 months','3–6 months','>6 months'].index(key)
        return key
    def evidence(rs):
        if len(ids)==1:
            if ids[0] in ['total_sales','average_won_deal','won_cycle']: rs=[r for r in rs if 'WON' in r['stage'].upper()]
            elif ids[0] in ['open_opportunities','weighted_pipeline']: rs=[r for r in rs if 'CLOSED' not in r['stage'].upper()]
            elif ids[0]=='open_cases': rs=[r for r in rs if r['closed_date'] is None]
            elif ids[0] in ['closed_cases','close_days']: rs=[r for r in rs if r['closed_date'] is not None]
        return sorted({r['id'] for r in rs})
    grouped=[dict(key=list(k) if isinstance(k,tuple) else k,values=select_metrics(groups[k]),record_ids=evidence(groups[k])) for k in sorted(groups,key=order)][:500]
    out=context(req,ds); out.update(values=select_metrics(rows),groups=grouped,row_count=len({r['id'] for r in rows}),previous=None)
    if len(groups)>500: out['warnings'].append('Grouped output limited to 500; narrow the filters.')
    if not rows: out['warnings'].append('No records match these filters.')
    if any(v is None for v in out['values'].values()): out['warnings'].append('— means no eligible denominator; it is not zero.')
    if req.period:
        length=(req.period.end-req.period.start).days+1
        prev=req.model_copy(update={'period':req.period.model_copy(update={'start':req.period.start-timedelta(days=length),'end':req.period.start-timedelta(days=1)})})
        out['previous']=select_metrics(filtered(allrows,prev))
    return serialize(out)

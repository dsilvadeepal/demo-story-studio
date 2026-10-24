from datetime import datetime,date,timezone
from decimal import Decimal as D
import pytest

def sales_rows():
    base=dict(created_at=datetime(2026,10,1,tzinfo=timezone.utc),close_date=datetime(2026,10,11,tzinfo=timezone.utc),account='Acme',account_type='Enterprise',industry='Technology',owner='Alex',type='New Business')
    return [dict(base,id=str(i),stage=stage,amount=D(amount),probability=D(prob)) for i,(stage,amount,prob) in enumerate([('Closed Won','300','100'),('Closed Lost','100','0'),('Qualification','200','50'),('Prospecting','400','25')])]

def test_sales_arithmetic():
    from app.queries.analytics import summarize
    v=summarize(sales_rows(),'sales',date(2026,10,21))
    assert v['total_sales']==D(300)
    assert v['win_rate']==D('.25')
    assert v['conversion']==D('.75')
    assert v['average_won_deal']==D(300)
    assert v['pipeline_generated']==D(1000)
    assert v['open_opportunities']==2
    assert v['weighted_pipeline']==D(200)
    assert v['won_cycle']==D(10)

def test_service_missing_and_duration():
    from app.queries.analytics import summarize
    start=datetime(2026,10,1,23,tzinfo=timezone.utc)
    rows=[dict(id=str(i),created_at=start,closed_date=datetime(2026,10,day,tzinfo=timezone.utc) if day else None,account=None if day is None else 'Acme') for i,day in enumerate([2,4,None])]
    v=summarize(rows,'service',date(2026,10,21))
    assert (v['created_cases'],v['closed_cases'],v['close_days'],v['missing_accounts'])==(3,2,D(2),1)
    assert summarize([],'sales',date(2026,10,21))['win_rate'] is None
    assert summarize([],'service',date(2026,10,21))['close_days'] is None

def test_buckets():
    from app.queries.analytics import days_bucket
    assert [days_bucket(n) for n in [-1,0,29,30,89,90,179,180]]==['Overdue','0–30 days','0–30 days','1–3 months','1–3 months','3–6 months','3–6 months','>6 months']

def test_query_filters_and_evidence():
    from app.db import engine
    from app.contracts import QueryRequest,RecordRequest
    from app.queries.analytics import query
    from app.queries.records import list_records,get_record
    from pydantic import ValidationError
    with engine().connect() as c:
        a=query(c,QueryRequest(dashboard='sales',metric_ids=['total_sales','open_opportunities']))
        assert a['values']['total_sales'] is not None
        assert a['dataset_id']=='baseline-v1-42-2026-10-21'
        with pytest.raises(ValueError): query(c,QueryRequest(dashboard='sales',filters={'bogus':['x']}))
        with pytest.raises(ValueError): query(c,QueryRequest(dashboard='sales',filters={'industry':['bogus']}))
        r=list_records(c,RecordRequest(dashboard='sales',entity='opportunities',page_size=2))
        r2=list_records(c,RecordRequest(dashboard='sales',entity='opportunities',page_size=2,cursor=r['next_cursor']))
        assert not {x['id'] for x in r['rows']}&{x['id'] for x in r2['rows']}
        detail=get_record(c,a['dataset_id'],'opportunities',r['rows'][0]['id'])
        assert len(detail['lines'])==3 and detail['account'] and detail['contacts']
        empty=query(c,QueryRequest(dashboard='sales',filters={'industry':['Technology'],'account_type':['Mid-market']}))
        assert empty['values']['win_rate'] is None

def test_period_boundaries_and_previous():
    from app.contracts import QueryRequest,Period
    from app.queries.analytics import filtered
    rows=sales_rows()
    req=QueryRequest(dashboard='sales',period=Period(start='2026-10-11',end='2026-10-11',field='close_date'))
    assert len(filtered(rows,req))==4
    assert not filtered(rows,req.model_copy(update={'period':Period(start='2026-10-12',end='2026-10-13',field='close_date')}))

def test_product_revenue_preserves_total_and_unknown_dataset_fails():
    from app.db import engine
    from app.contracts import QueryRequest
    from app.queries.analytics import query
    with engine().connect() as c:
        a=query(c,QueryRequest(dashboard='sales',metric_ids=['pipeline_generated']))
        b=query(c,QueryRequest(dashboard='sales',metric_ids=['pipeline_generated'],dimension='product'))
        assert sum(D(g['values']['pipeline_generated']) for g in b['groups'])==D(a['values']['pipeline_generated'])
        with pytest.raises(LookupError): query(c,QueryRequest(dashboard='sales',dataset_id='unknown'))

def test_chart_evidence_matches_selected_group():
    from app.db import engine
    from app.contracts import QueryRequest,RecordRequest
    from app.queries.analytics import query
    from app.queries.records import list_records
    with engine().connect() as c:
        q=query(c,QueryRequest(dashboard='service',metric_ids=['open_cases'],dimension='type_division'))
        group=next(g for g in q['groups'] if int(g['values']['open_cases'])>0)
        assert len(group['record_ids'])==int(group['values']['open_cases'])
        records=list_records(c,RecordRequest(dashboard='service',entity='cases',filters={'id':group['record_ids']}))
        assert records['total']==int(group['values']['open_cases'])
        assert all(r['closed_date'] is None for r in records['rows'])

def test_sql_preaggregation_uses_distinct_opportunities():
    from app.db import engine,tables,manifest
    from app.seed import generate
    from app.contracts import QueryRequest
    from app.queries.analytics import query
    b=generate(); ds='test-sql-fixture'
    with engine(admin=True).connect() as c:
        tx=c.begin()
        try:
            c.execute(manifest.insert(),dict(b['manifest'],id=ds))
            for table in ['accounts','users','products','pricebooks','pricebook_entries']:
                row=dict(b['tables'][table][0],dataset_id=ds)
                c.execute(tables[table].insert(),row)
            for i,r in enumerate(sales_rows()):
                c.execute(tables['opportunities'].insert(),dict(dataset_id=ds,id=r['id'],name='Fixture '+str(i),account_id='accounts-0000',owner_id='users-0000',type=r['type'],stage=r['stage'],probability=r['probability'],created_at=r['created_at'],close_date=r['close_date']))
                # Won opportunity has two lines, deliberately unlike other deals.
                for j,amount in enumerate([D(100),D(200)] if i==0 else [r['amount']]):
                    c.execute(tables['opportunity_line_items'].insert(),dict(dataset_id=ds,id=f'{i}-{j}',opportunity_id=r['id'],pricebook_entry_id='pricebook_entries-0000',quantity=D(1),unit_price=amount))
            q=query(c,QueryRequest(dashboard='sales',dataset_id=ds))
            assert D(q['values']['total_sales'])==300
            assert D(q['values']['win_rate'])==D('.25')
            assert D(q['values']['weighted_pipeline'])==200
            assert D(q['values']['won_cycle'])==10
        finally: tx.rollback()

def test_empty_evidence_ids_returns_no_records():
    from app.db import engine
    from app.contracts import RecordRequest
    from app.queries.records import list_records
    with engine().connect() as c:
        assert list_records(c,RecordRequest(dashboard='service',entity='cases',filters={'id':[]}))['total']==0

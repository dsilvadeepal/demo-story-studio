from datetime import date
from pathlib import Path
import pytest
from sqlalchemy import create_engine, text

def test_seed_repeatability():
    from app.seed import generate
    a=generate(42,date(2026,10,21)); b=generate(42,date(2026,10,21))
    assert a['manifest']['checksums']==b['manifest']['checksums']
    assert a['manifest']['counts']==dict(accounts=120,contacts=240,users=24,products=80,pricebooks=2,pricebook_entries=160,opportunities=1200,opportunity_line_items=3600,cases=2400)
    assert sum(c['account_id'] is None for c in a['tables']['cases'])==120
    assert {c['status'] for c in a['tables']['cases']} >= {'Working','New','Closed'}

def test_database_constraints():
    from app.db import engine, tables
    from app.seed import generate, load_baseline
    from sqlalchemy.exc import IntegrityError, DBAPIError
    bundle=generate(42,date(2026,10,21))
    with engine(admin=True).begin() as c: load_baseline(c,bundle)
    with engine(admin=True).begin() as c: assert load_baseline(c,bundle)['checksums']==bundle['manifest']['checksums']
    bad=dict(bundle['tables']['contacts'][0],id='invalid',account_id='missing')
    with pytest.raises(IntegrityError), engine(admin=True).begin() as c: c.execute(tables['contacts'].insert(),bad)
    bad=dict(bundle['tables']['opportunities'][0],id='invalid',close_date='2020-01-01T00:00:00+00:00')
    with pytest.raises(IntegrityError), engine(admin=True).begin() as c: c.execute(tables['opportunities'].insert(),bad)
    with pytest.raises(DBAPIError), engine().begin() as c: c.execute(text("UPDATE accounts SET name='changed'"))

def test_checksum_ignores_decimal_scale():
    from decimal import Decimal
    from app.seed import checksum
    assert checksum([{'id':'1','amount':Decimal('2')}])==checksum([{'id':'1','amount':Decimal('2.00')}])

def test_realistic_priority_status_coverage_and_history():
    from app.seed import generate
    bundle=generate(42,date(2026,10,21))
    for priority in ['Critical','High','Medium','Low']:
        rows=[r for r in bundle['tables']['cases'] if r['priority']==priority]
        assert any(r['closed_date'] is None for r in rows)
        assert any(r['closed_date'] is not None for r in rows)
    for name in ['opportunities','cases']:
        assert min(r['created_at'].date() for r in bundle['tables'][name])>=date(2024,10,21)

def test_seed_noop_rejects_live_content_drift():
    from app.seed import generate,load_baseline
    from app.db import engine,tables
    b=generate()
    with engine(admin=True).connect() as c:
        tx=c.begin()
        try:
            t=tables['accounts'];c.execute(t.update().where(t.c.dataset_id==b['manifest']['id'],t.c.id=='accounts-0000').values(name='Changed by privileged maintenance'))
            with pytest.raises(ValueError,match='stored records'):load_baseline(c,b)
        finally:tx.rollback()

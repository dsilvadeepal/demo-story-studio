from copy import deepcopy
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytest
from pydantic import ValidationError
from app.seed import generate
from app.scenarios.contracts import Proposal


def proposal(kind, dashboard='sales', ids=None, **params):
    return Proposal(parent_id='baseline-v1-42-2026-10-21', selection={'dashboard': dashboard,
        'record_ids': ids or ['opportunities-0000']}, operations=[{'kind':kind, **params}])


def test_prices_exact_and_parent_unchanged():
    from app.scenarios.operations import transform
    b=generate(); b['tables']['opportunity_line_items'][0]['unit_price']=Decimal('100.00')
    before=deepcopy(b)
    result=transform(b,proposal('scale_line_prices',factor='1.125'))
    assert result['tables']['opportunity_line_items'][0]['unit_price']==Decimal('112.50')
    assert result['tables']['opportunity_line_items'][0]['quantity']==before['tables']['opportunity_line_items'][0]['quantity']
    assert b==before


@pytest.mark.parametrize('stage,probability', [('Closed Won',100),('Closed Lost',0)])
def test_closed_stage_requires_correct_probability_and_explicit_date(stage,probability):
    from app.scenarios.operations import transform
    b=generate()
    with pytest.raises(ValueError): transform(b,proposal('set_stage',stage=stage,probability=probability))
    result=transform(b,proposal('set_stage',stage=stage,probability=probability,close_date='2026-10-20'))
    assert result['tables']['opportunities'][0]['probability']==probability
    with pytest.raises(ValueError): transform(b,proposal('set_stage',stage=stage,probability=50,close_date='2026-10-20'))


def test_date_order_and_resolution_round_half_up():
    from app.scenarios.operations import transform
    b=generate(); case=next(x for x in b['tables']['cases'] if x['status']=='Closed')
    case['created_at']=datetime(2026,10,1,13,tzinfo=timezone.utc)
    case['closed_date']=datetime(2026,10,4,13,tzinfo=timezone.utc)
    result=transform(b,proposal('adjust_resolution',dashboard='service',ids=[case['id']],factor='.5'))
    changed=next(x for x in result['tables']['cases'] if x['id']==case['id'])
    assert changed['closed_date']==datetime(2026,10,3,13,tzinfo=timezone.utc)
    with pytest.raises(ValueError): transform(b,proposal('set_expected_close',date='2000-01-01'))


def test_refresh_moves_both_domains_and_preserves_nulls_and_relationships():
    from app.scenarios.operations import transform
    from app.scenarios.validation import validate_candidate
    b=generate(); p=proposal('refresh_dates',day_offset=90); p=p.model_copy(update={'selection':p.selection.model_copy(update={'record_ids':[]})})
    result=transform(b,p)
    assert result['manifest']['as_of_date'].isoformat()=='2027-01-19'
    for name,fields in [('opportunities',['created_at','close_date']),('cases',['created_at','closed_date'])]:
        for old,new in zip(b['tables'][name],result['tables'][name]):
            for field in fields:
                assert new[field]==(old[field]+timedelta(days=90) if old[field] else None)
            assert new['account_id']==old['account_id']
    assert not validate_candidate(b,result,p).hard_errors
    result['tables']['accounts'][0]['name']='unauthorized'
    assert validate_candidate(b,result,p).hard_errors


def test_reject_overflow_conflicts_growth_and_unknown_fields():
    from app.scenarios.operations import transform
    from app.scenarios.validation import validate_candidate
    b=generate();p=proposal('scale_line_prices',factor='1.1')
    with pytest.raises(ValueError):transform(b,proposal('scale_line_prices',factor='1e30'))
    with pytest.raises(ValidationError):proposal('scale_line_prices',factor='1.1',sql='drop table')
    with pytest.raises(ValueError):transform(b,p.model_copy(update={'operations':p.operations*2}))
    changed=deepcopy(b);changed['tables']['cases'].pop()
    assert validate_candidate(b,changed,p).hard_errors


def test_top_five_ties_use_ascending_id(phase2_db):
    from sqlalchemy import text
    from app.scenarios.operations import resolve_selection
    p=Proposal(parent_id='baseline-v1-42-2026-10-21',selection={'dashboard':'sales','top_n':5},operations=[{'kind':'scale_line_prices','factor':1}])
    with phase2_db.admin.begin() as c:
        c.execute(text('UPDATE opportunity_line_items SET unit_price=100,quantity=1'))
        assert resolve_selection(c,p)==['opportunities-0000','opportunities-0001','opportunities-0002','opportunities-0003','opportunities-0004']


def test_reject_mixed_global_refresh_and_scoped_operations():
    from app.scenarios.operations import transform
    b=generate();p=proposal('refresh_dates',day_offset=90)
    p=p.model_copy(update={'selection':p.selection.model_copy(update={'record_ids':[]}),
        'operations':p.operations+proposal('scale_line_prices',factor='1.1').operations})
    with pytest.raises(ValueError):transform(b,p)


def test_reject_forged_manifest_and_out_of_scope_changes():
    from app.scenarios.validation import validate_candidate
    b=generate();p=proposal('scale_line_prices',factor='1.1')
    changed=deepcopy(b);changed['manifest']['semantic_version']='forged'
    assert validate_candidate(b,changed,p).hard_errors
    changed=deepcopy(b);changed['tables']['opportunity_line_items'][6]['unit_price']+=1
    assert validate_candidate(b,changed,p).hard_errors

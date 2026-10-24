import pytest
from decimal import Decimal
from sqlalchemy import text
from app.scenarios.contracts import OwnerContext, Proposal

OWNER=OwnerContext(owner_id='owner',workspace_id='local')
BASE='baseline-v1-42-2026-10-21'


def prepare(db):
    with db.admin.begin() as c:
        c.execute(text("SELECT studio_initialize('owner','local')"))
        role=c.dialect.identifier_preparer.quote(db.writer.url.username)
        c.execute(text(f'GRANT SELECT ON ALL TABLES IN SCHEMA public TO {role}'))
        c.execute(text(f'GRANT EXECUTE ON FUNCTION studio_publish(text,text,jsonb,text,text,jsonb,text,jsonb) TO {role}'))


def plan(factor='1.125'):
    return Proposal(parent_id=BASE,selection={'dashboard':'sales','record_ids':['opportunities-0000']},operations=[{'kind':'scale_line_prices','factor':factor}])


def test_candidate_retries_diffs_and_arithmetic(phase2_db):
    from app.scenarios.repository import create_candidate
    from app.scenarios.comparison import record_diff, compare
    from app.contracts import QueryRequest
    prepare(phase2_db)
    with phase2_db.admin.begin() as c:
        # Three $100 lines at quantities 1, 1, 1 => $300 -> $337.50.
        c.execute(text("UPDATE opportunity_line_items SET unit_price=100,quantity=1 WHERE opportunity_id='opportunities-0000'"))
    with phase2_db.writer.begin() as c:
        candidate=create_candidate(c,OWNER,plan(),'preview-key')
    # A disconnected client retries only after the original commit succeeded.
    with phase2_db.writer.begin() as c:
        assert create_candidate(c,OWNER,plan(),'preview-key').id==candidate.id
        with pytest.raises(ValueError):create_candidate(c,OWNER,plan('1.2'),'preview-key')
    with phase2_db.reader.connect() as c:
        result=compare(c,OWNER,BASE,candidate.id,QueryRequest(dashboard='sales',metric_ids=['pipeline_generated'],filters={'id':['opportunities-0000']}))
        assert Decimal(result.metric_deltas['pipeline_generated']['before'])==Decimal('300')
        assert Decimal(result.metric_deltas['pipeline_generated']['after'])==Decimal('337.50')
        cells=[];cursor=0
        while True:
            page=record_diff(c,OWNER,candidate.id,cursor,2);cells+=page['changes']
            if page['next_cursor'] is None:break
            cursor=page['next_cursor']
        assert len(cells)==3
        assert {x['field'] for x in cells}=={'unit_price'}
        assert c.scalar(text('SELECT count(*) FROM datasets'))==2
        assert c.scalar(text("SELECT unit_price FROM opportunity_line_items WHERE dataset_id=:id AND id='opportunity_line_items-0000'"),{'id':BASE})==100


def test_failure_rolls_back_and_baseline_checksums_unchanged(phase2_db):
    from app.scenarios.repository import create_candidate
    prepare(phase2_db)
    with phase2_db.reader.connect() as c:before=c.scalar(text('SELECT checksums::text FROM datasets'))
    with pytest.raises(RuntimeError):
        with phase2_db.writer.begin() as c:
            create_candidate(c,OWNER,plan(),'rollback-key')
            raise RuntimeError('simulate failure before transaction commit')
    with phase2_db.reader.connect() as c:
        assert c.scalar(text('SELECT count(*) FROM datasets'))==1
        assert c.scalar(text('SELECT checksums::text FROM datasets'))==before


def test_twentieth_version_is_last(phase2_db):
    from app.scenarios.repository import create_candidate
    prepare(phase2_db)
    with phase2_db.admin.begin() as c:
        for i in range(19):
            id='existing-'+str(i)
            c.execute(text('INSERT INTO datasets SELECT :id,revision,semantic_version,as_of_date,seed,generator_version,counts,checksums FROM datasets WHERE id=:base'),{'id':id,'base':BASE})
            c.execute(text("INSERT INTO studio_candidates(id,owner_id,workspace_id,parent_id,revision,content_hash,status) VALUES(:id,'owner','local',:base,:revision,'test','preview')"),{'id':id,'base':BASE,'revision':i+2})
    with phase2_db.writer.begin() as c:
        with pytest.raises(ValueError,match='LIMIT_REACHED'):
            create_candidate(c,OWNER,plan(),'over-limit')


def test_guarded_publication_rejects_relationship_change_atomically(phase2_db):
    from app.scenarios.repository import create_candidate, read_bundle, canonical
    from sqlalchemy.exc import DBAPIError
    from uuid import uuid4
    prepare(phase2_db)
    with phase2_db.writer.begin() as c:
        candidate=create_candidate(c,OWNER,plan(),'good')
    with phase2_db.writer.connect() as c:
        bundle=read_bundle(c,OWNER,candidate.id)
    id='candidate-'+str(uuid4());bundle['manifest'].update(id=id,revision=3)
    for rows in bundle['tables'].values():
        for row in rows:row['dataset_id']=id
    bundle['tables']['accounts'][0]['name']='Forbidden replacement'
    with pytest.raises(DBAPIError):
        with phase2_db.writer.begin() as c:
            c.execute(text("SELECT studio_publish('owner','local',CAST(:bundle AS jsonb),:hash,:hash,CAST(:proposal AS jsonb),'bad',CAST(:validation AS jsonb))"),
                {'bundle':canonical(bundle),'hash':'a'*64,'proposal':canonical(plan().model_dump(mode='json')),'validation':'{"hard_errors":[],"warnings":[]}'})
    with phase2_db.reader.connect() as c:
        assert c.scalar(text('SELECT count(*) FROM datasets'))==2


def test_date_comparison_labels_identical_and_aligned_periods(phase2_db):
    from app.scenarios.repository import create_candidate
    from app.scenarios.comparison import compare
    from app.contracts import QueryRequest
    prepare(phase2_db)
    p=Proposal(parent_id=BASE,selection={'dashboard':'sales'},operations=[{'kind':'refresh_dates','day_offset':90}])
    with phase2_db.writer.begin() as c: candidate=create_candidate(c,OWNER,p,'refresh')
    q=QueryRequest(dashboard='sales',metric_ids=['pipeline_generated'],period={'start':'2026-10-01','end':'2026-10-21'})
    with phase2_db.reader.connect() as c:
        same=compare(c,OWNER,BASE,candidate.id,q)
        aligned=compare(c,OWNER,BASE,candidate.id,q,aligned_period=True)
        assert any('identical absolute filters' in w for w in same.warnings)
        assert any('ALIGNED-PERIOD' in w for w in aligned.warnings)
        assert aligned.metric_deltas['pipeline_generated']['delta']=='0.0000'
        assert Decimal(same.metric_deltas['pipeline_generated']['delta'])!=0

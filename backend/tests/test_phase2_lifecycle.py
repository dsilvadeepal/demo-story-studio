import pytest
from sqlalchemy import text
from app.scenarios.contracts import ReviewEvent
from test_phase2_candidates import OWNER, BASE, plan, prepare


def ready(db):
    from app.scenarios.repository import create_candidate
    prepare(db)
    with db.admin.begin() as c:
        role=c.dialect.identifier_preparer.quote(db.writer.url.username)
        c.execute(text(f'GRANT EXECUTE ON FUNCTION studio_lifecycle(text,text,text,jsonb) TO {role}'))
    with db.writer.begin() as c:return create_candidate(c,OWNER,plan(),'candidate')


def test_approval_apply_idempotency_and_recovery(phase2_db):
    from app.scenarios.lifecycle import approve, apply, recover
    from app.scenarios.repository import get_active
    candidate=ready(phase2_db)
    with phase2_db.writer.begin() as c:
        with pytest.raises(ValueError,match='APPROVAL_REQUIRED'):apply(c,OWNER,'missing','no')
        approval=approve(c,OWNER,candidate.id,candidate.content_hash,BASE)
        assert get_active(c,OWNER).id==BASE
        activation=apply(c,OWNER,approval.id,'apply')
        assert get_active(c,OWNER).id==candidate.id
        assert apply(c,OWNER,approval.id,'apply')==activation
        recovered=recover(c,OWNER,BASE,candidate.id,'recover')
        assert recovered.active_id==BASE
        assert get_active(c,OWNER).id==BASE


@pytest.mark.parametrize('kind,changes_requested,valid',[('annotate',False,True),('annotate',True,False),('edit',False,False),('reject',False,False)])
def test_review_invalidation(phase2_db,kind,changes_requested,valid):
    from app.scenarios.lifecycle import approve,apply,record_review
    candidate=ready(phase2_db)
    with phase2_db.writer.begin() as c:
        approval=approve(c,OWNER,candidate.id,candidate.content_hash,BASE)
        record_review(c,OWNER,candidate.id,ReviewEvent(kind=kind,actor='owner',target='revision',reason='Please revise' if changes_requested else 'Review',changes_requested=changes_requested))
        if valid:assert apply(c,OWNER,approval.id,'apply').active_id==candidate.id
        else:
            with pytest.raises(ValueError,match='APPROVAL_REQUIRED'):apply(c,OWNER,approval.id,'apply')


def test_stale_tab_and_forged_hash_rejected(phase2_db):
    from app.scenarios.lifecycle import approve,apply
    from app.scenarios.repository import create_candidate
    first=ready(phase2_db)
    with phase2_db.writer.begin() as c:
        second=create_candidate(c,OWNER,plan('1.2'),'second')
        with pytest.raises(ValueError,match='STALE_VERSION'):approve(c,OWNER,first.id,'forged',BASE)
        a=approve(c,OWNER,first.id,first.content_hash,BASE)
        b=approve(c,OWNER,second.id,second.content_hash,BASE)
        apply(c,OWNER,b.id,'second-apply')
        with pytest.raises(ValueError,match='STALE_VERSION'):apply(c,OWNER,a.id,'first-apply')


def test_recovery_rejects_unapplied_preview_and_hard_validation(phase2_db):
    from app.scenarios.lifecycle import recover,approve
    candidate=ready(phase2_db)
    with phase2_db.writer.begin() as c:
        with pytest.raises(ValueError):recover(c,OWNER,candidate.id,BASE,'not-applied')
    with phase2_db.admin.begin() as c:
        c.execute(text("UPDATE opportunities SET probability=50 WHERE dataset_id=:id AND stage='Closed Won'"),{'id':candidate.id})
    with phase2_db.writer.begin() as c:
        with pytest.raises(ValueError,match='VALIDATION_FAILED'):approve(c,OWNER,candidate.id,candidate.content_hash,BASE)


def test_scenario_api_auth_origin_and_forged_revision(phase2_db,monkeypatch):
    from test_api import client
    from app.db import writer_engine
    candidate=ready(phase2_db)
    monkeypatch.setenv('STUDIO_WRITER_DATABASE_URL',phase2_db.writer.url.render_as_string(hide_password=False));writer_engine.cache_clear()
    api=client(monkeypatch)
    assert api.post('/api/v1/scenarios/approve',json={}).status_code==401
    api.post('/api/login',json={'password':'a-test-password-12345'})
    payload={'candidate_id':candidate.id,'expected_hash':'forged','expected_active_id':BASE}
    assert api.post('/api/v1/scenarios/approve',json=payload).status_code==409
    assert api.post('/api/v1/scenarios/approve',json=payload,headers={'origin':'https://evil.example'}).status_code==403
    assert api.post('/api/v1/scenarios/recover',json={'target_id':BASE,'expected_active_id':BASE,'key':'x','confirmed':False}).status_code==422
    writer_engine.cache_clear()


def test_new_preview_invalidates_pending_approval(phase2_db):
    from app.scenarios.lifecycle import approve,apply
    from app.scenarios.repository import create_candidate
    candidate=ready(phase2_db)
    with phase2_db.writer.begin() as c:
        approval=approve(c,OWNER,candidate.id,candidate.content_hash,BASE)
        create_candidate(c,OWNER,plan('1.2'),'refinement')
        with pytest.raises(ValueError,match='APPROVAL_REQUIRED'):apply(c,OWNER,approval.id,'old-approval')


def test_soft_warning_needs_reason_but_integrity_cannot_be_overridden(phase2_db):
    from app.scenarios.lifecycle import approve,record_review
    from app.scenarios.repository import create_candidate
    ready(phase2_db)
    with phase2_db.writer.begin() as c:
        candidate=create_candidate(c,OWNER,plan('1.5'),'large-change')
        with pytest.raises(ValueError,match='VALIDATION_FAILED'):approve(c,OWNER,candidate.id,candidate.content_hash,BASE)
        record_review(c,OWNER,candidate.id,ReviewEvent(kind='override',actor='owner',target='warnings',reason='Intentional synthetic stress scenario'))
        assert approve(c,OWNER,candidate.id,candidate.content_hash,BASE).candidate_id==candidate.id

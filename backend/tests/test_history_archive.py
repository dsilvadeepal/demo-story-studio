import pytest
from sqlalchemy import text
from app.scenarios.repository import create_candidate,read_bundle
from test_phase2_candidates import OWNER,BASE,prepare,plan


def test_cleanup_preserves_recent_selected_and_baseline_and_restores(phase2_db):
    prepare(phase2_db)
    with phase2_db.admin.begin() as c:
        created=[create_candidate(c,OWNER,plan(),f'archive-{i}') for i in range(6)]
        before=read_bundle(c,OWNER,created[0].id)
        count=c.scalar(text("SELECT studio_archive_history('owner','local','archive',:keep)"),{'keep':created[1].id})
        assert count==2
        assert read_bundle(c,OWNER,created[0].id)==before
        from app.scenarios.lifecycle import approve
        with pytest.raises(ValueError,match='Return this revision'):
            approve(c,OWNER,created[0].id,created[0].content_hash,BASE)
        assert c.scalar(text('SELECT archived_at IS NULL FROM studio_candidates WHERE id=:id'),{'id':BASE})
        for candidate in [created[1],*created[-3:]]:
            assert c.scalar(text('SELECT archived_at IS NULL FROM studio_candidates WHERE id=:id'),{'id':candidate.id})
        assert c.scalar(text("SELECT studio_archive_history('owner','local','restore',:id)"),{'id':created[0].id})==1
        assert c.scalar(text("SELECT studio_archive_history('owner','local','archive',:keep)"),{'keep':created[1].id})==1


def test_cleanup_rejects_other_owner(phase2_db):
    with phase2_db.admin.begin() as c:
        with pytest.raises(Exception,match='HISTORY_UNAVAILABLE'):
            c.execute(text("SELECT studio_archive_history('other','local','archive',NULL)"))


def test_cleanup_protects_approved_and_parent_revisions(phase2_db):
    from app.scenarios.lifecycle import approve
    prepare(phase2_db)
    with phase2_db.admin.begin() as c:
        rows=[create_candidate(c,OWNER,plan(),f'protected-{i}') for i in range(6)]
        create_candidate(c,OWNER,plan().model_copy(update={'parent_id':rows[1].id}),'child')
        approve(c,OWNER,rows[0].id,rows[0].content_hash,BASE)
        c.execute(text("SELECT studio_archive_history('owner','local','archive',NULL)"))
        for row in rows[:2]:
            assert c.scalar(text('SELECT archived_at IS NULL FROM studio_candidates WHERE id=:id'),{'id':row.id})


def test_archive_frees_slots_in_database_publish_guard(phase2_db):
    prepare(phase2_db)
    with phase2_db.admin.begin() as c:
        for i in range(19):create_candidate(c,OWNER,plan(),f'capacity-{i}')
        assert c.scalar(text("SELECT studio_archive_history('owner','local','archive',NULL)"))==16
        new=create_candidate(c,OWNER,plan(),'after-cleanup')
        assert new.revision==21
        assert c.scalar(text('SELECT count(*) FROM studio_candidates'))==21
        assert c.scalar(text('SELECT count(*) FROM studio_candidates WHERE archived_at IS NULL'))==5

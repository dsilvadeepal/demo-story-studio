"""Authority tests use real PostgreSQL roles, not mocked permission failures."""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError


def test_baseline_registered_and_scoped(phase2_db):
    from app.scenarios.contracts import OwnerContext
    from app.scenarios.repository import get_active, get_candidate
    owner = OwnerContext(owner_id='owner', workspace_id='local')
    with phase2_db.admin.begin() as c:
        c.execute(text("SELECT studio_initialize('owner','local')"))
    with phase2_db.reader.connect() as c:
        active = get_active(c, owner)
        assert active.id == 'baseline-v1-42-2026-10-21'
        assert active.status == 'baseline'
        with pytest.raises(LookupError):
            get_candidate(c, OwnerContext(owner_id='other', workspace_id='local'), active.id)


@pytest.mark.parametrize('role', ['reader', 'writer'])
def test_runtime_cannot_mutate_business_or_control_rows(phase2_db, role):
    with phase2_db.admin.begin() as c:
        c.execute(text("SELECT studio_initialize('owner','local')"))
    for sql in ["UPDATE opportunities SET probability=5", "UPDATE datasets SET revision=9",
                "UPDATE studio_candidates SET content_hash='forged'",
                "UPDATE studio_active SET dataset_id='forged'"]:
        with getattr(phase2_db, role).connect() as c:
            with pytest.raises(DBAPIError):
                c.execute(text(sql))


def test_parent_revision_unique_and_dataset_fk(phase2_db):
    with phase2_db.admin.begin() as c:
        c.execute(text("SELECT studio_initialize('owner','local')"))
        c.execute(text("INSERT INTO datasets SELECT 'candidate-1',2,semantic_version,as_of_date,seed,generator_version,counts,checksums FROM datasets LIMIT 1"))
        c.execute(text("INSERT INTO datasets SELECT 'candidate-2',2,semantic_version,as_of_date,seed,generator_version,counts,checksums FROM datasets LIMIT 1"))
        sql = "INSERT INTO studio_candidates (id,owner_id,workspace_id,parent_id,revision,content_hash,status) VALUES (:id,'owner','local','baseline-v1-42-2026-10-21',2,'hash','preview')"
        c.execute(text(sql), {'id':'candidate-1'})
        with pytest.raises(IntegrityError), c.begin_nested():
            c.execute(text(sql), {'id':'candidate-2'})
        with pytest.raises(IntegrityError), c.begin_nested():
            c.execute(text("UPDATE opportunity_line_items SET dataset_id='candidate-1' WHERE id='opportunity_line_items-0000'"))


def test_writer_engine_never_falls_back_to_admin(monkeypatch):
    from app.db import writer_engine
    monkeypatch.delenv('STUDIO_WRITER_DATABASE_URL', raising=False)
    writer_engine.cache_clear()
    with pytest.raises(RuntimeError, match='STUDIO_WRITER_DATABASE_URL'):
        writer_engine()


def test_upgrade_existing_foundation_and_repeated_setup_preserve_baseline(phase2_db):
    import importlib.util
    from pathlib import Path
    from app.seed import generate, load_baseline
    spec = importlib.util.spec_from_file_location('local_setup', Path(__file__).resolve().parents[2] / 'scripts/setup_local.py')
    setup = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(setup)
    with phase2_db.admin.begin() as c:
        before = c.scalar(text('SELECT checksums::text FROM datasets LIMIT 1'))
        setup.configure_scenario_access(c, phase2_db.reader.url.username, phase2_db.writer.url.username)
        setup.configure_scenario_access(c, phase2_db.reader.url.username, phase2_db.writer.url.username)
        load_baseline(c, generate())
        assert c.scalar(text('SELECT checksums::text FROM datasets LIMIT 1')) == before
    with phase2_db.writer.connect() as c:
        assert c.scalar(text('SELECT count(*) FROM studio_active')) == 1
        with pytest.raises(DBAPIError):
            c.execute(text("SELECT studio_initialize('owner','local')"))

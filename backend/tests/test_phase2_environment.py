"""Catch fixture targeting the owner's DB or hiding uncommitted test state."""
import pytest
from sqlalchemy import text


def test_phase2_db_is_isolated(phase2_db):
    assert phase2_db.name != phase2_db.app_database
    assert phase2_db.name.startswith('studio_test_')
    with pytest.raises(ValueError):
        phase2_db.validate_drop(phase2_db.app_database)
    with phase2_db.admin.begin() as c:
        c.execute(text('CREATE TABLE isolation_probe (value integer)'))
        c.execute(text('INSERT INTO isolation_probe VALUES (41)'))
    with phase2_db.admin.connect() as c:
        assert c.scalar(text('SELECT value FROM isolation_probe')) == 41
        assert c.scalar(text('SELECT count(*) FROM datasets')) == 1
    with phase2_db.reader.connect() as c:
        assert c.scalar(text('SELECT count(*) FROM opportunities')) == 1200

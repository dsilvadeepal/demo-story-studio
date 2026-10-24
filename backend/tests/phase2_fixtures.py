"""Disposable PostgreSQL fixtures; never migrate or seed the owner's database."""
import os
import re
import secrets
import uuid
from dataclasses import dataclass
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.db import engine
from app.seed import generate, load_baseline

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class TestDatabase:
    name: str
    app_database: str
    admin: object
    reader: object
    writer: object

    def validate_drop(self, name):
        if name != self.name or name == self.app_database or not re.fullmatch(r'studio_test_[a-f0-9]{32}', name):
            raise ValueError('Refusing cleanup outside the allocated disposable database')


@pytest.fixture
def phase2_db(monkeypatch):
    raw = os.getenv('PHASE2_TEST_ADMIN_URL')
    if not raw:
        raw = (ROOT / '.local/admin-url').read_text().strip()
    source = make_url(raw)
    if source.host not in ('127.0.0.1', 'localhost'):
        raise ValueError('Disposable tests require loopback PostgreSQL')
    name = 'studio_test_' + uuid.uuid4().hex
    cluster = create_engine(source.set(database='postgres'), isolation_level='AUTOCOMMIT', hide_parameters=True)
    admin = create_engine(source.set(database=name), hide_parameters=True)
    password = secrets.token_hex(24)
    roles = [name + '_reader', name + '_writer']
    testdb = TestDatabase(name, source.database, admin,
        create_engine(source.set(database=name, username=roles[0], password=password), hide_parameters=True),
        create_engine(source.set(database=name, username=roles[1], password=password), hide_parameters=True))
    created = False
    try:
        with cluster.connect() as c:
            c.execute(text(f'CREATE DATABASE "{name}"'))
            created = True
            for role in roles:
                c.execute(text(f'CREATE ROLE "{role}" LOGIN PASSWORD \'{password}\''))
        monkeypatch.setenv('MIGRATION_DATABASE_URL', source.set(database=name).render_as_string(hide_password=False))
        monkeypatch.setenv('APP_DATABASE_URL', source.set(database=name, username=roles[0], password=password).render_as_string(hide_password=False))
        engine.cache_clear()
        config = Config(str(ROOT / 'backend/alembic.ini'))
        config.set_main_option('script_location', str(ROOT / 'backend/migrations'))
        command.upgrade(config, '001')
        with admin.begin() as c:
            load_baseline(c, generate())
        command.upgrade(config, 'head')
        with admin.begin() as c:
            load_baseline(c, generate())
            c.execute(text("SELECT studio_initialize('owner','local')"))
            c.execute(text(f'GRANT USAGE ON SCHEMA public TO "{roles[0]}", "{roles[1]}"'))
            c.execute(text(f'GRANT SELECT ON ALL TABLES IN SCHEMA public TO "{roles[0]}"'))
        yield testdb
    finally:
        engine.cache_clear()
        for e in (testdb.admin, testdb.reader, testdb.writer):
            e.dispose()
        testdb.validate_drop(name)
        with cluster.connect() as c:
            if created:
                c.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
            for role in roles:
                c.execute(text(f'DROP ROLE IF EXISTS "{role}"'))
        cluster.dispose()

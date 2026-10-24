import pytest
from phase2_fixtures import phase2_db


@pytest.fixture(autouse=True)
def isolated_database_for_suite(phase2_db):
    """Existing integration tests must never fall back to the owner's database."""
    yield

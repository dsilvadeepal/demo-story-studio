from sqlalchemy import text
from test_phase2_candidates import prepare,plan,OWNER,BASE
from app.scenarios.repository import create_candidate


def test_catalog_and_manifest_resolve_authorized_dataset(phase2_db,monkeypatch):
    from test_api import client
    prepare(phase2_db)
    with phase2_db.writer.begin() as c:candidate=create_candidate(c,OWNER,plan(),'catalog')
    with phase2_db.admin.begin() as c:c.execute(text("UPDATE accounts SET name='Candidate-only account' WHERE dataset_id=:id AND id='accounts-0000'"),{'id':candidate.id})
    api=client(monkeypatch);api.post('/api/login',json={'password':'a-test-password-12345'})
    assert api.get('/api/v1/dataset').json()['id']==BASE
    assert api.get('/api/v1/dataset',params={'dataset_id':candidate.id}).json()['id']==candidate.id
    active=api.get('/api/v1/catalog').json()
    preview=api.get('/api/v1/catalog',params={'dataset_id':candidate.id}).json()
    assert 'Candidate-only account' not in active['options']['sales']['account']
    assert 'Candidate-only account' in preview['options']['sales']['account']
    assert api.get('/api/v1/dataset',params={'dataset_id':'foreign'}).status_code==404

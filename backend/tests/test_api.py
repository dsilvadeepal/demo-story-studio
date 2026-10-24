import pytest
from fastapi.testclient import TestClient

def client(monkeypatch):
    from app.auth import hash_password
    monkeypatch.setenv('OWNER_PASSWORD_HASH',hash_password('a-test-password-12345'))
    monkeypatch.setenv('SESSION_SECRET','test-only-session-key-at-least-32-characters')
    monkeypatch.setenv('STUDIO_LOCAL','1')
    from app.main import app
    return TestClient(app)

def test_auth_and_read_api(monkeypatch):
    c=client(monkeypatch)
    assert c.get('/api/v1/dataset').status_code==401
    assert c.post('/api/login',json={'password':'wrong'}).status_code==401
    assert c.post('/api/login',json={'password':'a-test-password-12345'}).status_code==200
    m=c.get('/api/v1/dataset').json()
    assert m['counts']['cases']==2400
    assert c.get('/api/v1/catalog').status_code==200
    assert c.post('/api/v1/query',json={'dashboard':'sales','metric_ids':['total_sales']}).json()['values']['total_sales']
    assert c.post('/api/v1/query',json={'dashboard':'sales','filters':{'bad':['bad']}}).status_code==422
    assert c.post('/api/v1/query',json={'dashboard':'sales','dataset_id':'bad'}).status_code==404
    assert c.post('/api/v1/records',json={'dashboard':'sales','entity':'opportunities','page_size':101}).status_code==422
    assert c.post('/api/v1/apply',json={}).status_code==404
    assert c.post('/api/logout').status_code==200
    assert c.get('/api/v1/dataset').status_code==401

def test_cross_origin_login_rejected(monkeypatch):
    c=client(monkeypatch)
    assert c.post('/api/login',headers={'origin':'https://evil.example'},json={'password':'a-test-password-12345'}).status_code==403

def test_expired_session(monkeypatch):
    c=client(monkeypatch)
    c.cookies.set('studio_session','invalid')
    assert c.get('/api/v1/dataset').status_code==401

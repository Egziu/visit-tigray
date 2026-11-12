from fastapi.testclient import TestClient
from app.main import app

def test_frontend_assets():
    client=TestClient(app)
    page=client.get('/')
    assert page.status_code==200
    assert 'VISIT <b>TIGRAY</b>' in page.text
    assert 'The Tigray Memories Awards' in page.text
    assert client.get('/static/style.css').status_code==200
    assert client.get('/static/app.js').status_code==200

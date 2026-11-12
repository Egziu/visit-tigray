import os
import tempfile
from pathlib import Path

_tmp=tempfile.TemporaryDirectory()
os.environ['DATABASE_PATH']=str(Path(_tmp.name)/'test.sqlite3')
os.environ['ADMIN_TOKEN']='test-only-strong-admin-token'
from fastapi.testclient import TestClient
from app.main import app
client=TestClient(app)

def test_health_and_discovery():
    assert client.get('/api/health').json()['status']=='ok'
    r=client.get('/api/destinations')
    assert r.status_code==200 and len(r.json())>=6
    assert client.get('/api/destinations/unknown').status_code==404

def test_plan_has_safety_warning():
    r=client.post('/api/plan',json={'interests':['history'],'days':3})
    assert r.status_code==200
    assert 'Not a confirmed travel route' in r.json()['notice']

def test_memory_moderation_and_access_control():
    payload={'display_name':'Traveler','title':'Memory of mountains','story':'A long and thoughtful account of a day learning from local people and their histories.','destination':'Gheralta','consent':True}
    r=client.post('/api/memories',json=payload)
    assert r.status_code==201
    ident=r.json()['id']
    assert not any(x['id']==ident for x in client.get('/api/memories').json())
    assert client.get('/api/admin/overview').status_code==401
    h={'X-Admin-Token':'test-only-strong-admin-token'}
    assert client.get('/api/admin/overview',headers=h).status_code==200
    assert client.patch('/api/admin/memories/'+ident,headers=h,json={'status':'approved'}).status_code==200
    assert any(x['id']==ident for x in client.get('/api/memories').json())
    assert client.get('/api/admin/audit',headers=h).json()

def test_invalid_or_unconsented_memory():
    payload={'display_name':'Traveler','title':'A beautiful memory','story':'This is my original story about a meaningful journey into the past.','destination':'Aksum','consent':False}
    assert client.post('/api/memories',json=payload).status_code==400
    payload['consent']=True
    payload['image_url']='javascript:alert(1)'
    assert client.post('/api/memories',json=payload).status_code==422

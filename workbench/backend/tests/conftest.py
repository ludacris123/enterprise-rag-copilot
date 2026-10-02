import os
import re
import pytest
from fastapi.testclient import TestClient
os.environ.setdefault('DATABASE_URL','sqlite:///./test-workbench.db')
os.environ.update(EAGER_JOBS='true',ARTIFACT_DIR='./test-artifacts',APP_ENV='test')
from app.main import app, local_buckets
from app.db import Base, engine, SessionLocal
from app.models import EmailOutbox

@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(engine);Base.metadata.create_all(engine);local_buckets.clear()
    yield
    Base.metadata.drop_all(engine)
    import shutil
    shutil.rmtree('test-artifacts',ignore_errors=True)

@pytest.fixture
def client():
    with TestClient(app) as c:yield c

def email_token(email,purpose):
    with SessionLocal() as db:
        rows=db.query(EmailOutbox).filter_by(recipient=email).order_by(EmailOutbox.created_at.desc()).all()
        row=next(r for r in rows if f'action={purpose}' in r.body)
        return re.search(r'token=([\w-]+)',row.body).group(1)

def account(client,email='owner@example.com',name='Owner User'):
    r=client.post('/api/auth/signup',json={'email':email,'name':name,'password':'SecurePass123!'})
    assert r.status_code==201,r.text
    r=client.post('/api/auth/verify',json={'token':email_token(email,'verify')});assert r.status_code==200,r.text
    r=client.post('/api/auth/login',json={'email':email,'password':'SecurePass123!'});assert r.status_code==200,r.text
    h={'Authorization':'Bearer '+r.json()['access_token']}
    return h,client.get('/api/workspaces',headers=h).json()[0]['id'],r.json()['user']

@pytest.fixture
def owner(client):return account(client)

def upload(client,h,wid,content='Customers may request a refund within 30 days. Travel claims must be filed within 14 days.'):
    r=client.post(f'/api/w/{wid}/documents',headers=h,files={'file':('policy.md',content,'text/markdown')})
    assert r.status_code==202,r.text
    assert r.json()['status']=='succeeded',r.text
    return r.json()['result']['document_id']

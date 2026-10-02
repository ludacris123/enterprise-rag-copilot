import time
from sqlalchemy import select
from app.db import SessionLocal
from app.models import ActionToken,User
from conftest import email_token
ORIGIN={'Origin':'http://localhost:5173'}

def test_signup_verification_and_password_policy(client):
    for password in ['weak','OnlyLettersHere']:
        assert client.post('/api/auth/signup',json={'email':'new@example.com','name':'New User','password':password}).status_code==422
    assert client.post('/api/auth/signup',json={'email':'new@example.com','name':'New User','password':'SecurePass123!'}).status_code==201
    assert client.post('/api/auth/login',json={'email':'new@example.com','password':'SecurePass123!'}).status_code==403
    token=email_token('new@example.com','verify')
    assert client.post('/api/auth/verify',json={'token':token}).status_code==200
    assert client.post('/api/auth/verify',json={'token':token}).status_code==400

def test_hash_and_authentication(client,owner):
    h,_,u=owner
    with SessionLocal() as db:assert db.get(User,u['id']).password_hash.startswith('$argon2id$')
    assert 'password' not in client.get('/api/me',headers=h).text
    assert client.get('/api/me').status_code==401
    assert client.post('/api/auth/login',json={'email':'owner@example.com','password':'wrong'}).status_code==401

def test_refresh_rotation_reuse_revokes_access(client,owner):
    h,_,_=owner
    original=client.cookies.get('refresh_token')
    r=client.post('/api/auth/refresh',headers=ORIGIN);assert r.status_code==200,r.text
    assert client.cookies.get('refresh_token')!=original
    rotated={'Authorization':'Bearer '+r.json()['access_token']}
    client.cookies.clear();client.cookies.set('refresh_token',original)
    assert client.post('/api/auth/refresh',headers=ORIGIN).status_code==401
    assert client.get('/api/me',headers=rotated).status_code==401
    assert client.get('/api/me',headers=h).status_code==401

def test_cookie_origin_check(client,owner):
    for endpoint in ['refresh','logout']:
        assert client.post('/api/auth/'+endpoint,headers={'Origin':'https://evil.example'}).status_code==403
        assert client.post('/api/auth/'+endpoint).status_code==403

def test_logout_revokes_access(client,owner):
    h,_,_=owner
    assert client.post('/api/auth/logout',headers=ORIGIN).status_code==200
    assert client.get('/api/me',headers=h).status_code==401

def test_reset_revokes_sessions_and_token_single_use(client,owner):
    h,_,_=owner
    unknown=client.post('/api/auth/forgot-password',json={'email':'unknown@example.com'})
    r=client.post('/api/auth/forgot-password',json={'email':'owner@example.com'});assert unknown.json()==r.json()
    token=email_token('owner@example.com','reset')
    payload={'token':token,'password':'ChangedPass456!'}
    assert client.post('/api/auth/reset-password',json=payload).status_code==200
    assert client.get('/api/me',headers=h).status_code==401
    assert client.post('/api/auth/reset-password',json=payload).status_code==400
    assert client.post('/api/auth/login',json={'email':'owner@example.com','password':'ChangedPass456!'}).status_code==200

def test_expired_link(client):
    client.post('/api/auth/signup',json={'email':'expired@example.com','name':'Expired User','password':'SecurePass123!'})
    token=email_token('expired@example.com','verify')
    with SessionLocal() as db:
        row=db.scalar(select(ActionToken));row.expires_at=time.time()-1;db.commit()
    assert client.post('/api/auth/verify',json={'token':token}).status_code==400

def test_change_password(client,owner):
    h,_,_=owner
    assert client.post('/api/me/password',headers=h,json={'current_password':'wrong','password':'Changed12345!'}).status_code==400
    assert client.post('/api/me/password',headers=h,json={'current_password':'SecurePass123!','password':'Changed12345!'}).status_code==200
    assert client.get('/api/me',headers=h).status_code==401

def test_login_throttle(client):
    codes=[client.post('/api/auth/login',json={'email':'unknown@example.com','password':'wrong'}).status_code for _ in range(11)]
    assert codes[-1]==429

def test_whitespace_name_rejected(client):
    r=client.post('/api/auth/signup',json={'email':'empty@example.com','name':'    ','password':'SecurePass123!'})
    assert r.status_code==422

def test_session_listing_and_revocation(client,owner):
    h,_,_=owner
    sessions=client.get('/api/me/sessions',headers=h).json()
    assert len(sessions)==1 and 'refresh_hash' not in sessions[0]
    assert client.delete('/api/me/sessions/'+sessions[0]['id'],headers=h).status_code==200
    assert client.get('/api/me',headers=h).status_code==401

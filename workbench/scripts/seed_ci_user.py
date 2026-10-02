"""Isolated browser-test fixture; not included in runtime images."""
import os
if os.environ.get('CI') != 'true':
    raise SystemExit('This fixture is for an isolated CI database only')
from app.db import SessionLocal
from app.models import User, Workspace, Membership
from app.security import hasher
with SessionLocal() as db:
    user=User(email='browser-ci@example.com',name='Browser CI Reviewer',password_hash=hasher.hash('BrowserTest123!'),verified=True)
    db.add(user);db.flush()
    workspace=Workspace(name='Browser CI workspace')
    db.add(workspace);db.flush()
    db.add(Membership(workspace_id=workspace.id,user_id=user.id,role='owner'))
    db.commit()
print('Created isolated browser-test fixture')

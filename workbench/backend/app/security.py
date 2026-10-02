import hashlib
import secrets
import time
from datetime import datetime, timedelta, timezone
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import Depends, HTTPException, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session
from .config import get_settings
from .db import get_db
from .models import User, LoginSession, Membership, ActionToken, EmailOutbox, Audit

hasher = PasswordHasher()
bearer = HTTPBearer(auto_error=False)
DUMMY_HASH = hasher.hash("not-a-real-account-password")


def digest(value: str):
    return hashlib.sha256(value.encode()).hexdigest()


def check_password(password, hashed):
    try:
        return hasher.verify(hashed, password)
    except VerificationError:
        return False


def access_token(session: LoginSession):
    cfg = get_settings()
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": session.user_id, "sid": session.id, "type": "access", "iat": now,
                       "exp": now + timedelta(minutes=cfg.access_minutes), "iss": "workbench", "aud": "workbench-api"},
                      cfg.jwt_secret, algorithm="HS256")


def set_refresh(response: Response, value: str):
    cfg = get_settings()
    response.set_cookie("refresh_token", value, httponly=True, secure=cfg.cookie_secure,
                        samesite="strict", path="/api/auth", max_age=cfg.refresh_days * 86400)


def issue_session(db: Session, user: User, response: Response):
    raw = secrets.token_urlsafe(48)
    row = LoginSession(user_id=user.id, refresh_hash=digest(raw), expires_at=time.time() + get_settings().refresh_days * 86400)
    db.add(row)
    db.flush()
    set_refresh(response, raw)
    return {"access_token": access_token(row), "token_type": "bearer", "user": public_user(user)}


def public_user(user):
    return {"id": user.id, "email": user.email, "name": user.name, "verified": user.verified}


def current_user(credential: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)):
    if not credential:
        raise HTTPException(401, "Sign in to continue")
    try:
        claims = jwt.decode(credential.credentials, get_settings().jwt_secret, algorithms=["HS256"],
                            issuer="workbench", audience="workbench-api", options={"require": ["exp", "sub", "sid", "type"]})
        if claims["type"] != "access":
            raise ValueError()
        row = db.get(LoginSession, claims["sid"])
        user = db.get(User, claims["sub"])
        if not row or row.revoked or row.expires_at < time.time() or row.user_id != claims["sub"] or not user or not user.verified:
            raise ValueError()
        return user
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(401, "Session expired; sign in again")


def member(db, user, workspace_id, write=False, admin=False):
    row = db.scalar(select(Membership).where(Membership.workspace_id == workspace_id, Membership.user_id == user.id))
    if not row:
        raise HTTPException(404, "Workspace not found")
    if (write and row.role == "viewer") or (admin and row.role not in ("owner", "admin")):
        raise HTTPException(403, "Your workspace role does not allow this action")
    return row


def cookie_origin(request: Request):
    # Every browser cookie-authenticated mutation must carry the expected origin.
    if request.headers.get("origin") != get_settings().frontend_url:
        raise HTTPException(403, "Invalid request origin")


def action_email(db, user, purpose):
    # Invalidate earlier unused tokens of the same purpose before issuing another.
    for old in db.scalars(select(ActionToken).where(ActionToken.user_id == user.id, ActionToken.purpose == purpose, ActionToken.used.is_(False))):
        old.used = True
    token = secrets.token_urlsafe(48)
    db.add(ActionToken(token_hash=digest(token), user_id=user.id, purpose=purpose, expires_at=time.time() + 1800))
    url = f"{get_settings().frontend_url}/?action={purpose}&token={token}"
    db.add(EmailOutbox(recipient=user.email, subject="Verify your account" if purpose == "verify" else "Reset your password",
                       body=f"Open this link within 30 minutes:\n{url}\n\nIf you did not request this, ignore this message."))


def consume_action(db, token, purpose):
    row = db.scalar(select(ActionToken).where(ActionToken.token_hash == digest(token)).with_for_update())
    if not row or row.used or row.purpose != purpose or row.expires_at < time.time():
        raise HTTPException(400, "This link is invalid or expired")
    row.used = True
    return db.get(User, row.user_id)


def audit(db, workspace_id, user_id, action, resource_id=None):
    db.add(Audit(workspace_id=workspace_id, user_id=user_id, action=action, resource_id=resource_id))

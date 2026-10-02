import io
import json
import logging
import secrets
import time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, Depends, HTTPException, Request, Response, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool
from sqlalchemy import select, func, delete, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from pypdf import PdfReader
from redis import Redis
from redis.exceptions import RedisError
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from .config import get_settings
from .db import get_db
from .models import (User, Workspace, Membership, LoginSession, UsedRefresh, Document, Chunk, Job,
                     Trace, EvaluationDataset, Audit, Note)
from .schemas import (Signup, Login, EmailRequest, TokenRequest, Reset, ChangePassword, WorkspaceInput,
                      MemberInput, RunInput, DatasetInput, EvalInput, PredictInput)
from .security import (hasher, check_password, DUMMY_HASH, digest, current_user, issue_session, set_refresh,
                       access_token, public_user, cookie_origin, action_email, consume_action, member, audit)
from .guardrails import redact, inspect_input
from .providers import capabilities
from .worker import execute
from .ml import predict

cfg = get_settings()
app = FastAPI(title="AI Engineering Workbench", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=[cfg.frontend_url], allow_credentials=True,
                   allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["Authorization", "Content-Type", "X-Request-ID"])
logger = logging.getLogger("workbench.api")
logging.basicConfig(level=logging.INFO, format="%(message)s")
REQUESTS = Counter("workbench_requests_total", "HTTP requests", ["method", "route", "status"])
LATENCY = Histogram("workbench_request_seconds", "HTTP latency", ["route"])
redis = Redis.from_url(cfg.redis_url, socket_connect_timeout=1, socket_timeout=1)
local_buckets = defaultdict(list)


def rate_limit(key, maximum=30, window=60):
    key = "limit:" + digest(key)
    try:
        if cfg.app_env == "test":
            raise RedisError("Deterministic test limiter")
        count = redis.eval("local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]) end; return n", 1, key, window)
    except RedisError:
        if cfg.app_env == "production":
            raise HTTPException(503, "Rate limiting service unavailable")
        now = time.time()
        local_buckets[key] = [t for t in local_buckets[key] if t > now - window]
        local_buckets[key].append(now)
        count = len(local_buckets[key])
    if count > maximum:
        raise HTTPException(429, "Too many requests; try again shortly", headers={"Retry-After": str(window)})


@app.middleware("http")
async def observe(request: Request, call_next):
    start = time.perf_counter()
    request_id = str(uuid.uuid4())
    if request.url.path.startswith("/api/auth"):
        try:
            await run_in_threadpool(rate_limit, "auth:" + (request.client.host if request.client else "unknown"))
        except HTTPException as exc:
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers)
    response = await call_next(request)
    route = getattr(request.scope.get("route"), "path", "unmatched")
    elapsed = time.perf_counter() - start
    REQUESTS.labels(request.method, route, response.status_code).inc()
    LATENCY.labels(route).observe(elapsed)
    response.headers.update({"X-Request-ID": request_id, "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer",
                             "Cache-Control": "no-store"})
    logger.info(json.dumps({"request_id": request_id, "method": request.method, "route": route, "status": response.status_code, "ms": round(elapsed * 1000, 1)}))
    return response


@app.get("/health/live")
def live():
    return {"status": "ok"}


@app.get("/health/ready")
def ready(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        if not cfg.eager_jobs:
            redis.ping()
        return {"status": "ready"}
    except Exception:
        raise HTTPException(503, "Database or queue unavailable")


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/api/auth/signup", status_code=201)
def signup(body: Signup, db: Session = Depends(get_db)):
    email = str(body.email).lower()
    rate_limit("signup:" + email, 3, 3600)
    if db.scalar(select(User).where(User.email == email)):
        # Same response for existing accounts; don't disclose registration status.
        return {"message": "If this address is eligible, a verification email will arrive shortly"}
    user = User(email=email, name=body.name.strip(), password_hash=hasher.hash(body.password))
    db.add(user)
    db.flush()
    workspace = Workspace(name=f"{user.name.split()[0]}'s workspace")
    db.add(workspace)
    db.flush()
    db.add(Membership(workspace_id=workspace.id, user_id=user.id, role="owner"))
    action_email(db, user, "verify")
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    return {"message": "If this address is eligible, a verification email will arrive shortly"}


@app.post("/api/auth/verify")
def verify(body: TokenRequest, db: Session = Depends(get_db)):
    user = consume_action(db, body.token, "verify")
    user.verified = True
    db.commit()
    return {"message": "Email verified. You can now sign in."}


@app.post("/api/auth/resend-verification")
def resend(body: EmailRequest, db: Session = Depends(get_db)):
    rate_limit("resend:" + str(body.email).lower(), 3, 3600)
    user = db.scalar(select(User).where(User.email == str(body.email).lower()))
    if user and not user.verified:
        action_email(db, user, "verify")
        db.commit()
    return {"message": "If verification is needed, an email will arrive shortly"}


@app.post("/api/auth/login")
def login(body: Login, response: Response, db: Session = Depends(get_db)):
    rate_limit("login:" + str(body.email).lower(), 10, 900)
    user = db.scalar(select(User).where(User.email == str(body.email).lower()))
    valid = check_password(body.password, user.password_hash if user else DUMMY_HASH)
    if not user or not valid:
        raise HTTPException(401, "Invalid email or password")
    if not user.verified:
        raise HTTPException(403, "Verify your email before signing in")
    result = issue_session(db, user, response)
    db.commit()
    return result


@app.post("/api/auth/refresh", dependencies=[Depends(cookie_origin)])
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    raw = request.cookies.get("refresh_token", "")
    hashed = digest(raw)
    used = db.get(UsedRefresh, hashed)
    if used:
        row = db.get(LoginSession, used.session_id)
        row.revoked = True
        db.commit()
        raise HTTPException(401, "Refresh token reuse detected; sign in again")
    row = db.scalar(select(LoginSession).where(LoginSession.refresh_hash == hashed).with_for_update())
    if not row or row.revoked or row.expires_at < time.time():
        raise HTTPException(401, "Session expired")
    user = db.get(User, row.user_id)
    if not user or not user.verified:
        raise HTTPException(401, "Account unavailable")
    replacement = secrets.token_urlsafe(48)
    db.add(UsedRefresh(token_hash=hashed, session_id=row.id))
    row.refresh_hash = digest(replacement)
    # Absolute expiry: rotation does not extend the original session indefinitely.
    db.commit()
    set_refresh(response, replacement)
    return {"access_token": access_token(row), "user": public_user(user)}


@app.post("/api/auth/logout", dependencies=[Depends(cookie_origin)])
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    hashed = digest(request.cookies.get("refresh_token", ""))
    row = db.scalar(select(LoginSession).where(LoginSession.refresh_hash == hashed))
    if row:
        row.revoked = True
        db.commit()
    response.delete_cookie("refresh_token", path="/api/auth", secure=cfg.cookie_secure, httponly=True, samesite="strict")
    return {"message": "Signed out"}


@app.post("/api/auth/forgot-password")
def forgot(body: EmailRequest, db: Session = Depends(get_db)):
    rate_limit("reset:" + str(body.email).lower(), 3, 3600)
    user = db.scalar(select(User).where(User.email == str(body.email).lower()))
    if user:
        action_email(db, user, "reset")
        db.commit()
    return {"message": "If this account exists, a reset email will arrive shortly"}


@app.post("/api/auth/reset-password")
def reset(body: Reset, db: Session = Depends(get_db)):
    user = consume_action(db, body.token, "reset")
    user.password_hash = hasher.hash(body.password)
    for row in db.scalars(select(LoginSession).where(LoginSession.user_id == user.id)):
        row.revoked = True
    db.commit()
    return {"message": "Password changed. Sign in again."}


@app.get("/api/me")
def me(user: User = Depends(current_user)):
    return public_user(user)


@app.post("/api/me/password")
def change_password(body: ChangePassword, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not check_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    user.password_hash = hasher.hash(body.password)
    for row in db.scalars(select(LoginSession).where(LoginSession.user_id == user.id)):
        row.revoked = True
    db.commit()
    return {"message": "Password changed. All sessions have been revoked."}


@app.get("/api/providers")
def providers(user: User = Depends(current_user)):
    return {"providers": capabilities(), "embedding_mode": cfg.embedding_mode, "limits": {"documents": cfg.max_documents, "runs_per_day": cfg.max_runs_per_day, "chunks": cfg.max_chunks}}


@app.get("/api/workspaces")
def workspaces(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [{"id": w.id, "name": w.name, "role": m.role} for w, m in db.execute(select(Workspace, Membership).join(Membership).where(Membership.user_id == user.id))]


@app.post("/api/workspaces", status_code=201)
def create_workspace(body: WorkspaceInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if db.scalar(select(func.count()).select_from(Membership).where(Membership.user_id == user.id)) >= 10:
        raise HTTPException(409, "Workspace limit reached")
    row = Workspace(name=body.name)
    db.add(row)
    db.flush()
    db.add(Membership(workspace_id=row.id, user_id=user.id, role="owner"))
    audit(db, row.id, user.id, "workspace.created", row.id)
    db.commit()
    return {"id": row.id, "name": row.name, "role": "owner"}


@app.get("/api/w/{wid}/members")
def members(wid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    member(db, user, wid)
    return [{"id": m.id, "name": u.name, "email": u.email, "role": m.role} for m, u in db.execute(select(Membership, User).join(User).where(Membership.workspace_id == wid))]


@app.post("/api/w/{wid}/members")
def add_member(wid: str, body: MemberInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    actor = member(db, user, wid, admin=True)
    if body.role == "admin" and actor.role != "owner":
        raise HTTPException(403, "Only owners can grant admin access")
    target = db.scalar(select(User).where(User.email == str(body.email).lower(), User.verified.is_(True)))
    if not target:
        raise HTTPException(400, "Ask this person to register and verify an account first")
    if db.scalar(select(Membership).where(Membership.workspace_id == wid, Membership.user_id == target.id)):
        raise HTTPException(409, "This person is already a member")
    db.add(Membership(workspace_id=wid, user_id=target.id, role=body.role))
    audit(db, wid, user.id, "member.added", target.id)
    db.commit()
    return {"message": "Member added"}


@app.delete("/api/w/{wid}/members/{mid}")
def remove_member(wid: str, mid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    actor = member(db, user, wid, admin=True)
    target = db.get(Membership, mid)
    if not target or target.workspace_id != wid:
        raise HTTPException(404, "Member not found")
    if target.role == "owner" or (target.role == "admin" and actor.role != "owner"):
        raise HTTPException(403, "Only owners can remove admins; the owner cannot be removed")
    db.delete(target)
    audit(db, wid, user.id, "member.removed", mid)
    db.commit()
    return {"message": "Member removed"}


def workspace_lock(db, wid):
    return db.scalar(select(Workspace).where(Workspace.id == wid).with_for_update())


def make_job(db, wid, user, kind, payload):
    workspace_lock(db, wid)
    day_start = int(time.time() // 86400) * 86400
    count = db.scalar(select(func.count()).select_from(Job).where(Job.workspace_id == wid, Job.created_at >= day_start))
    if count >= cfg.max_runs_per_day:
        raise HTTPException(429, "Daily workspace run quota reached")
    row = Job(workspace_id=wid, user_id=user.id, kind=kind, payload=payload)
    db.add(row)
    db.flush()
    audit(db, wid, user.id, f"{kind}.submitted", row.id)
    db.commit()
    # Persist first; the outbox dispatcher retries queue outages without losing the request.
    if cfg.eager_jobs:
        execute(row.id)
        db.expire_all()
        row = db.get(Job, row.id)
    return job_dict(row)


def job_dict(row):
    return {"id": row.id, "kind": row.kind, "status": row.status, "result": row.result,
            "error": row.error, "attempts": row.attempts, "created_at": row.created_at,
            "finished_at": row.finished_at, "question": row.payload.get("question"), "provider": row.payload.get("provider")}


@app.get("/api/w/{wid}/documents")
def documents(wid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    member(db, user, wid)
    return [{"id": d.id, "name": d.name, "status": d.status, "created_at": d.created_at,
             "chunks": db.scalar(select(func.count()).select_from(Chunk).where(Chunk.document_id == d.id, Chunk.workspace_id == wid))}
            for d in db.scalars(select(Document).where(Document.workspace_id == wid).order_by(Document.created_at.desc()))]


@app.post("/api/w/{wid}/documents", status_code=202)
def upload_document(wid: str, file: UploadFile = File(...), user: User = Depends(current_user), db: Session = Depends(get_db)):
    member(db, user, wid, write=True)
    data = file.file.read(cfg.max_upload_bytes + 1)
    if len(data) > cfg.max_upload_bytes:
        raise HTTPException(413, "File exceeds 5 MB limit")
    name = Path(file.filename or "document.txt").name[:200]
    extension = Path(name).suffix.lower()
    try:
        if extension == ".pdf":
            pdf = PdfReader(io.BytesIO(data))
            if pdf.is_encrypted or len(pdf.pages) > 100:
                raise ValueError()
            content = "\n".join((p.extract_text() or "") for p in pdf.pages)
        elif extension in (".txt", ".md"):
            content = data.decode("utf-8")
        else:
            raise HTTPException(415, "Upload a text PDF, TXT, or Markdown file")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(400, "The file could not be read; scanned PDFs require OCR first")
    if not content.strip() or len(content) > 250000:
        raise HTTPException(400, "Document must contain 1–250,000 text characters")
    workspace_lock(db, wid)
    if db.scalar(select(func.count()).select_from(Document).where(Document.workspace_id == wid)) >= cfg.max_documents:
        raise HTTPException(409, "Document quota reached")
    # Reserve capacity for queued documents too, not only already indexed chunks.
    stored = db.scalar(select(func.count()).select_from(Chunk).where(Chunk.workspace_id == wid))
    pending = db.scalars(select(Document).where(Document.workspace_id == wid, Document.status != "ready")).all()
    from .retrieval import split_text
    reserved = sum(len(split_text(d.content)) for d in pending)
    if stored + reserved + len(split_text(content)) > cfg.max_chunks:
        raise HTTPException(409, "Workspace chunk quota reached")
    hashed = digest(content)
    if db.scalar(select(Document).where(Document.workspace_id == wid, Document.content_hash == hashed)):
        raise HTTPException(409, "This document is already in the workspace")
    doc = Document(workspace_id=wid, name=name, content_hash=hashed, content=content)
    db.add(doc)
    db.flush()
    return make_job(db, wid, user, "ingestion", {"document_id": doc.id})


@app.delete("/api/w/{wid}/documents/{did}")
def delete_document(wid: str, did: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    member(db, user, wid, write=True)
    doc = db.get(Document, did)
    if not doc or doc.workspace_id != wid:
        raise HTTPException(404, "Document not found")
    pending = db.scalar(select(Job).where(Job.workspace_id == wid, Job.kind == "ingestion", Job.status.in_(["queued", "running"])).limit(1))
    if pending:
        raise HTTPException(409, "Wait for ingestion jobs to finish before deleting documents")
    db.execute(delete(Chunk).where(Chunk.document_id == did, Chunk.workspace_id == wid))
    db.delete(doc)
    audit(db, wid, user.id, "document.deleted", did)
    db.commit()
    return {"message": "Document deleted"}


@app.post("/api/w/{wid}/runs/{kind}", status_code=202)
def run(wid: str, kind: Literal["chat", "agent"], body: RunInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    member(db, user, wid, write=True)
    enabled = {p["id"] for p in capabilities() if p["enabled"]}
    if body.provider not in enabled:
        raise HTTPException(400, "Configure the provider's API key on the server first")
    payload = body.model_dump()
    payload["question"] = redact(body.question)
    return make_job(db, wid, user, kind, payload)


@app.get("/api/w/{wid}/jobs")
def jobs(wid: str, limit: int = 30, user: User = Depends(current_user), db: Session = Depends(get_db)):
    member(db, user, wid)
    if not 1 <= limit <= 100:
        raise HTTPException(422, "Limit must be between 1 and 100")
    return [job_dict(j) for j in db.scalars(select(Job).where(Job.workspace_id == wid).order_by(Job.created_at.desc()).limit(limit))]


@app.get("/api/w/{wid}/jobs/{jid}")
def job(wid: str, jid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    member(db, user, wid)
    row = db.get(Job, jid)
    if not row or row.workspace_id != wid:
        raise HTTPException(404, "Run not found")
    return job_dict(row)


@app.post("/api/w/{wid}/jobs/{jid}/{decision}")
def approve(wid: str, jid: str, decision: Literal["approve", "reject"], user: User = Depends(current_user), db: Session = Depends(get_db)):
    member(db, user, wid, admin=True)
    row = db.scalar(select(Job).where(Job.id == jid, Job.workspace_id == wid).with_for_update())
    if not row:
        raise HTTPException(404, "Run not found")
    if row.status != "awaiting_approval":
        raise HTTPException(409, "Run is not awaiting approval")
    if decision == "approve":
        db.add(Note(workspace_id=wid, job_id=row.id, text=row.result["proposed_note"]))
    row.status = "approved" if decision == "approve" else "rejected"
    audit(db, wid, user.id, f"agent.{decision}", jid)
    db.commit()
    return job_dict(row)


@app.get("/api/w/{wid}/notes")
def notes(wid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    member(db, user, wid)
    return [{"id": n.id, "text": n.text, "job_id": n.job_id} for n in db.scalars(select(Note).where(Note.workspace_id == wid).order_by(Note.created_at.desc()).limit(100))]


@app.get("/api/w/{wid}/datasets")
def datasets(wid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    member(db, user, wid)
    return [{"id": d.id, "name": d.name, "cases": d.cases} for d in db.scalars(select(EvaluationDataset).where(EvaluationDataset.workspace_id == wid))]


@app.post("/api/w/{wid}/datasets", status_code=201)
def create_dataset(wid: str, body: DatasetInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    member(db, user, wid, write=True)
    workspace_lock(db, wid)
    if db.scalar(select(func.count()).select_from(EvaluationDataset).where(EvaluationDataset.workspace_id == wid)) >= 30:
        raise HTTPException(409, "Evaluation dataset quota reached")
    cases = [c.model_dump() for c in body.cases]
    for case in cases:
        case["question"] = redact(case["question"])
        case["expected_answer"] = redact(case["expected_answer"])
        for did in case["expected_document_ids"]:
            doc = db.get(Document, did)
            if not doc or doc.workspace_id != wid:
                raise HTTPException(400, "Expected documents must belong to this workspace")
    row = EvaluationDataset(workspace_id=wid, name=body.name, cases=cases)
    db.add(row)
    db.flush()
    audit(db, wid, user.id, "dataset.created", row.id)
    db.commit()
    return {"id": row.id, "name": row.name, "cases": row.cases}


@app.post("/api/w/{wid}/evaluations", status_code=202)
def evaluate(wid: str, body: EvalInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    member(db, user, wid, write=True)
    dataset = db.get(EvaluationDataset, body.dataset_id)
    if not dataset or dataset.workspace_id != wid:
        raise HTTPException(404, "Dataset not found")
    if not any(p["id"] == body.provider and p["enabled"] for p in capabilities()):
        raise HTTPException(400, "Provider is not configured")
    if body.judge and body.provider == "offline":
        raise HTTPException(400, "LLM judging requires Groq, OpenAI, or a local model")
    return make_job(db, wid, user, "evaluation", body.model_dump())


@app.post("/api/w/{wid}/ml/train", status_code=202)
def ml_train(wid: str, file: UploadFile = File(...), target: str = Form(...),
             task: Literal["classification", "regression"] = Form("classification"),
             algorithm: Literal["linear", "random_forest"] = Form("linear"),
             user: User = Depends(current_user), db: Session = Depends(get_db)):
    member(db, user, wid, write=True)
    raw = file.file.read(cfg.max_upload_bytes + 1)
    if len(raw) > cfg.max_upload_bytes:
        raise HTTPException(413, "CSV exceeds 5 MB limit")
    try:
        data = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(400, "Use a UTF-8 CSV")
    return make_job(db, wid, user, "ml_training", {"csv": data, "target": target, "task": task, "algorithm": algorithm})


@app.post("/api/w/{wid}/ml/{jid}/predict")
def ml_predict(wid: str, jid: str, body: PredictInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    member(db, user, wid, write=True)
    rate_limit("predict:" + user.id, 30, 60)
    row = db.get(Job, jid)
    if not row or row.workspace_id != wid or row.kind != "ml_training" or row.status != "succeeded":
        raise HTTPException(404, "Trained model not found")
    try:
        return predict(row.id, body.rows)
    except (ValueError, FileNotFoundError):
        raise HTTPException(400, "Model artifact unavailable or prediction columns invalid")


@app.get("/api/w/{wid}/traces")
def traces(wid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    member(db, user, wid)
    return [{"id": t.id, "job_id": t.job_id, "provider": t.provider, "model": t.model, "latency_ms": t.latency_ms,
             "input_tokens": t.input_tokens, "output_tokens": t.output_tokens, "blocked": t.blocked, "details": t.details,
             "created_at": t.created_at} for t in db.scalars(select(Trace).where(Trace.workspace_id == wid).order_by(Trace.created_at.desc()).limit(100))]


@app.get("/api/w/{wid}/audit")
def audits(wid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    member(db, user, wid, admin=True)
    return [{"id": a.id, "action": a.action, "user_id": a.user_id, "resource_id": a.resource_id, "created_at": a.created_at}
            for a in db.scalars(select(Audit).where(Audit.workspace_id == wid).order_by(Audit.created_at.desc()).limit(100))]


@app.get("/api/w/{wid}/overview")
def overview(wid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    member(db, user, wid)
    trace_rows = db.scalars(select(Trace).where(Trace.workspace_id == wid).order_by(Trace.created_at.desc()).limit(100)).all()
    latencies = sorted(t.latency_ms for t in trace_rows)
    return {"documents": db.scalar(select(func.count()).select_from(Document).where(Document.workspace_id == wid)),
            "runs": db.scalar(select(func.count()).select_from(Job).where(Job.workspace_id == wid)),
            "pending_approvals": db.scalar(select(func.count()).select_from(Job).where(Job.workspace_id == wid, Job.status == "awaiting_approval")),
            "tokens": sum(t.input_tokens + t.output_tokens for t in trace_rows),
            "p95_latency_ms": latencies[min(len(latencies) - 1, int(len(latencies) * 0.95))] if latencies else 0,
            "blocked": sum(t.blocked for t in trace_rows), "sample_size": len(trace_rows)}


from .schemas import QuantReport


@app.post("/api/w/{wid}/quantization-reports", status_code=201)
def quant_report(wid: str, body: QuantReport, user: User = Depends(current_user), db: Session = Depends(get_db)):
    member(db, user, wid, write=True)
    workspace_lock(db, wid)
    count = db.scalar(select(func.count()).select_from(Job).where(Job.workspace_id == wid, Job.kind == "quantization_report"))
    if count >= 30:
        raise HTTPException(409, "Quantization report quota reached")
    report = body.model_dump()
    report["prompt"] = redact(report["prompt"])
    for measurement in report["measurements"]:
        measurement["output"] = redact(measurement["output"])
    row = Job(workspace_id=wid, user_id=user.id, kind="quantization_report", payload={}, result=report, status="succeeded", finished_at=time.time())
    db.add(row)
    db.flush()
    audit(db, wid, user.id, "quantization_report.imported", row.id)
    db.commit()
    return job_dict(row)


@app.get("/api/me/sessions")
def sessions(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [{"id": row.id, "created_at": row.created_at, "expires_at": row.expires_at, "revoked": row.revoked}
            for row in db.scalars(select(LoginSession).where(LoginSession.user_id == user.id).order_by(LoginSession.created_at.desc()).limit(30))]


@app.delete("/api/me/sessions/{sid}")
def revoke_session(sid: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = db.get(LoginSession, sid)
    if not row or row.user_id != user.id:
        raise HTTPException(404, "Session not found")
    row.revoked = True
    db.commit()
    return {"message": "Session revoked"}

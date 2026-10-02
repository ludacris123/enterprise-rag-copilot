import logging
import smtplib
import time
from email.message import EmailMessage
import httpx
from celery import Celery
from sqlalchemy import select
from .config import get_settings
from .db import SessionLocal
from .models import Job, Document, EvaluationDataset, EmailOutbox, Note
from .retrieval import index_document
from .pipelines import rag, run_agent
from .evaluation import evaluate
from .ml import train_model
from .providers import ProviderError

cfg = get_settings()
celery = Celery("workbench", broker=cfg.redis_url)
celery.conf.update(task_acks_late=True, task_reject_on_worker_lost=True, worker_prefetch_multiplier=1,
                   task_soft_time_limit=240, task_time_limit=300,
                   beat_schedule={"dispatch-outbox": {"task": "app.worker.dispatch", "schedule": 5.0}},
                   broker_transport_options={"visibility_timeout": 600})
logger = logging.getLogger("workbench.worker")


def safe_error(exc):
    if isinstance(exc, ProviderError):
        return str(exc)
    if isinstance(exc, httpx.HTTPStatusError):
        return f"Model provider returned HTTP {exc.response.status_code}; check the model name, key, and quota"
    if isinstance(exc, httpx.TransportError):
        return "Model provider could not be reached"
    if isinstance(exc, ValueError):
        return str(exc)[:250]
    return "The job failed; check worker logs using its job ID"


@celery.task(name="app.worker.execute")
def execute(job_id):
    with SessionLocal() as db:
        job = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
        if not job or job.status not in ("queued",):
            return
        job.status, job.started_at = "running", time.time()
        job.attempts += 1
        db.commit()
    try:
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if job.kind == "ingestion":
                doc = db.get(Document, job.payload["document_id"])
                if not doc or doc.workspace_id != job.workspace_id:
                    raise ValueError("Document no longer exists")
                if doc.status != "ready":
                    index_document(db, doc)
                result = {"document_id": doc.id, "status": "ready"}
            elif job.kind == "chat":
                result = rag(db, job.workspace_id, job.payload, job.id)
            elif job.kind == "agent":
                result = run_agent(db, job.workspace_id, job.payload, job.id)
            elif job.kind == "evaluation":
                dataset = db.get(EvaluationDataset, job.payload["dataset_id"])
                if not dataset or dataset.workspace_id != job.workspace_id:
                    raise ValueError("Evaluation dataset no longer exists")
                result = evaluate(db, job.workspace_id, job.payload, dataset.cases, job.id)
            elif job.kind == "ml_training":
                result = train_model(job.payload, job.id)
                job.payload = {k: v for k, v in job.payload.items() if k != "csv"}
            else:
                raise ValueError("Unknown job kind")
            job.result = result
            job.status = "awaiting_approval" if result.get("proposed_note") else "succeeded"
            job.finished_at = time.time()
            db.commit()
    except Exception as exc:
        logger.error("job_failed id=%s type=%s", job_id, type(exc).__name__)
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            transient = isinstance(exc, httpx.TransportError) or (isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in (429, 500, 502, 503, 504))
            job.status = "queued" if transient and job.attempts < 3 else "failed"
            job.error = safe_error(exc)
            job.finished_at = time.time()
            if job.kind == "ingestion" and job.status == "failed":
                doc = db.get(Document, job.payload["document_id"])
                if doc:
                    doc.status = "failed"
            if job.kind == "ml_training" and job.status == "failed":
                job.payload = {k: v for k, v in job.payload.items() if k != "csv"}
            db.commit()


@celery.task(name="app.worker.send_email")
def send_email(email_id):
    with SessionLocal() as db:
        row = db.scalar(select(EmailOutbox).where(EmailOutbox.id == email_id).with_for_update())
        if not row or row.status != "pending" or row.attempts >= 5:
            return
        row.attempts += 1
        try:
            message = EmailMessage()
            message["From"], message["To"], message["Subject"] = cfg.mail_from, row.recipient, row.subject
            message.set_content(row.body)
            with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=10) as smtp:
                if cfg.smtp_starttls:
                    smtp.starttls()
                if cfg.smtp_username:
                    smtp.login(cfg.smtp_username, cfg.smtp_password)
                smtp.send_message(message)
            row.status = "sent"
            # Don't keep bearer links after delivery.
            row.body = "[Delivered]"
        except (OSError, smtplib.SMTPException):
            if row.attempts >= 5:
                row.status = "failed"
            logger.warning("email_delivery_failed id=%s attempt=%s", row.id, row.attempts)
        db.commit()


@celery.task(name="app.worker.dispatch")
def dispatch():
    with SessionLocal() as db:
        # A killed worker leaves a recoverable persisted job; timeout is longer than task hard limit.
        stale = db.scalars(select(Job).where(Job.status == "running", Job.started_at < time.time() - 600)).all()
        for job in stale:
            job.status = "queued" if job.attempts < 3 else "failed"
            job.error = "Worker interrupted; recovered by scheduler" if job.attempts < 3 else "Worker repeatedly interrupted"
        db.commit()
        ids = db.scalars(select(Job.id).where(Job.status == "queued").limit(100)).all()
        emails = db.scalars(select(EmailOutbox.id).where(EmailOutbox.status == "pending", EmailOutbox.attempts < 5).limit(50)).all()
    for job_id in ids:
        execute.delay(job_id)
    for email_id in emails:
        send_email.delay(email_id)

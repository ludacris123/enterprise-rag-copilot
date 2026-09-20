from celery import Celery
from app.config import settings
from app.ingestion import ingest

celery = Celery("copilot", broker=settings().redis_url, backend=settings().redis_url)

@celery.task(autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def ingest_document(title: str, text: str, tenant_id: str, metadata: dict[str, str]):
    document_id, chunks = ingest(title, text, tenant_id, metadata)
    return {"document_id": document_id, "chunks": chunks}

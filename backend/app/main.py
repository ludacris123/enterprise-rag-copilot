from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app
from app.api import router
from app.config import settings
from app.ingestion import ingest
from app.observability import MetricsMiddleware

@asynccontextmanager
async def lifespan(_: FastAPI):
    ingest(
        "Employee Travel Policy",
        "Employees may claim domestic travel expenses within 30 days. Claims above INR 25000 require manager approval. Original receipts are required.",
        "demo-tenant", {"department": "finance"},
    )
    ingest(
        "Security Handbook",
        "Never share passwords, OTPs, recovery codes, or complete payment card numbers. Report suspicious requests to the security team.",
        "demo-tenant", {"department": "security"},
    )
    yield

app = FastAPI(title=settings().app_name, version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings().cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.add_middleware(MetricsMiddleware)
app.include_router(router, prefix=settings().api_prefix)
app.mount("/metrics", make_asgi_app())

@app.get("/health/live")
async def live():
    return {"status": "ok"}

@app.get("/health/ready")
async def ready():
    return {"status": "ready", "model_mode": settings().model_mode}

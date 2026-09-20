import time
from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

REQUESTS = Counter("copilot_requests_total", "API requests", ["method", "path", "status"])
LATENCY = Histogram("copilot_request_duration_seconds", "Request latency", ["path"])
logger = structlog.get_logger()

class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start
        REQUESTS.labels(request.method, request.url.path, response.status_code).inc()
        LATENCY.labels(request.url.path).observe(elapsed)
        logger.info("request_complete", path=request.url.path, status=response.status_code, latency=elapsed)
        return response

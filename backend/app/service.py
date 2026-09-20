import time
from uuid import uuid4
from app.config import settings
from app.generation import generate
from app.guardrails import inspect_input, redact_pii, validate_citations
from app.retrieval import retriever
from app.schemas import ChatResponse, Citation

async def answer(question: str, tenant_id: str, filters: dict[str, str]) -> ChatResponse:
    started, trace_id = time.perf_counter(), str(uuid4())
    decision = inspect_input(question, settings().max_input_chars)
    if not decision.allowed:
        return ChatResponse(
            answer="This request was blocked by the safety policy.",
            citations=[], conversation_id=str(uuid4()), trace_id=trace_id,
            grounded=False, latency_ms=(time.perf_counter() - started) * 1000,
        )
    safe_question = redact_pii(question).value
    hits = retriever.search(safe_question, tenant_id, settings().top_k, filters)
    raw = await generate(safe_question, hits)
    safe_answer = redact_pii(raw).value
    grounded = validate_citations(safe_answer, [hit.chunk.text for hit in hits])
    citations = [
        Citation(
            document_id=hit.chunk.document_id, title=hit.chunk.title,
            chunk_id=hit.chunk.chunk_id, excerpt=hit.chunk.text[:280], score=round(hit.score, 4),
        ) for hit in hits
    ]
    return ChatResponse(
        answer=safe_answer, citations=citations, conversation_id=str(uuid4()),
        trace_id=trace_id, grounded=grounded,
        latency_ms=round((time.perf_counter() - started) * 1000, 2),
    )

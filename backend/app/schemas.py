from typing import Literal
from pydantic import BaseModel, Field

Role = Literal["viewer", "analyst", "admin"]

class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=6000)
    conversation_id: str | None = None
    filters: dict[str, str] = {}

class Citation(BaseModel):
    document_id: str
    title: str
    chunk_id: str
    excerpt: str
    score: float

class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    conversation_id: str
    trace_id: str
    grounded: bool
    latency_ms: float

class IngestResponse(BaseModel):
    document_id: str
    chunks_created: int
    status: str

class FeedbackRequest(BaseModel):
    trace_id: str
    rating: Literal[-1, 1]
    reason: str | None = Field(default=None, max_length=500)

class EvalResult(BaseModel):
    dataset: str
    total: int
    passed: int
    pass_rate: float
    metrics: dict[str, float]

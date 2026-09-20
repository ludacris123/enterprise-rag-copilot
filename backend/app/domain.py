from dataclasses import dataclass, field
from uuid import uuid4

@dataclass
class Chunk:
    document_id: str
    title: str
    text: str
    tenant_id: str
    metadata: dict[str, str] = field(default_factory=dict)
    chunk_id: str = field(default_factory=lambda: str(uuid4()))
    embedding: list[float] | None = None

@dataclass
class SearchHit:
    chunk: Chunk
    score: float
    dense_score: float = 0.0
    sparse_score: float = 0.0

import re
from uuid import uuid4
from app.domain import Chunk
from app.retrieval import retriever

def chunk_text(text: str, size: int = 900, overlap: int = 120) -> list[str]:
    clean = re.sub(r"\s+", " ", text).strip()
    if not clean:
        return []
    chunks, start = [], 0
    while start < len(clean):
        end = min(len(clean), start + size)
        if end < len(clean):
            boundary = clean.rfind(" ", start, end)
            end = boundary if boundary > start + size // 2 else end
        chunks.append(clean[start:end])
        if end == len(clean):
            break
        start = max(start + 1, end - overlap)
    return chunks

def ingest(title: str, text: str, tenant_id: str, metadata: dict[str, str]) -> tuple[str, int]:
    document_id = str(uuid4())
    chunks = [Chunk(document_id, title, part, tenant_id, metadata) for part in chunk_text(text)]
    retriever.index(chunks)
    return document_id, len(chunks)

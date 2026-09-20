import math
import re
from collections import Counter
from app.domain import Chunk, SearchHit

class HybridRetriever:
    """In-memory reference implementation; production adapter uses pgvector + Postgres FTS."""

    def __init__(self) -> None:
        self.chunks: list[Chunk] = []

    def index(self, chunks: list[Chunk]) -> None:
        self.chunks.extend(chunks)

    @staticmethod
    def _tokens(text: str) -> list[str]:
        return re.findall(r"[a-z0-9]+", text.lower())

    def _sparse(self, query: str, text: str) -> float:
        q, d = Counter(self._tokens(query)), Counter(self._tokens(text))
        return sum(min(q[t], d[t]) for t in q) / max(1, sum(q.values()))

    def _dense_demo(self, query: str, text: str) -> float:
        # Deterministic local proxy. Replace with cosine distance over pgvector in production.
        q, d = set(self._tokens(query)), set(self._tokens(text))
        return len(q & d) / math.sqrt(max(1, len(q) * len(d)))

    def search(self, query: str, tenant_id: str, top_k: int, filters: dict[str, str]) -> list[SearchHit]:
        hits = []
        for chunk in self.chunks:
            if chunk.tenant_id != tenant_id:
                continue
            if any(chunk.metadata.get(k) != v for k, v in filters.items()):
                continue
            sparse, dense = self._sparse(query, chunk.text), self._dense_demo(query, chunk.text)
            score = 0.45 * sparse + 0.55 * dense
            if score > 0:
                hits.append(SearchHit(chunk, score, dense, sparse))
        return sorted(hits, key=lambda hit: hit.score, reverse=True)[:top_k]

retriever = HybridRetriever()

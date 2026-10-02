import math
import re
from collections import Counter
from functools import lru_cache
import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer, ENGLISH_STOP_WORDS
from sqlalchemy import select
from .config import get_settings
from .models import Chunk, Document
from .guardrails import redact

HASH = HashingVectorizer(n_features=256, alternate_sign=False, norm="l2", stop_words="english")


@lru_cache(maxsize=1)
def semantic_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(get_settings().embedding_model)


def model_id():
    cfg = get_settings()
    return "hashing-256-v1" if cfg.embedding_mode == "hashing" else cfg.embedding_model


def embed(texts):
    if get_settings().embedding_mode == "hashing":
        return HASH.transform(texts).toarray().tolist()
    return semantic_model().encode(texts, normalize_embeddings=True).tolist()


def split_text(text, size=1800, overlap=250):
    text = text.replace("\x00", "").strip()
    return [text[start:start + size] for start in range(0, len(text), size - overlap) if text[start:start + size].strip()]


def index_document(db, doc):
    # Redact before embedding/storage so retrieved contexts and source previews are safe.
    parts = split_text(redact(doc.content))
    vectors = embed(parts)
    existing = {c.ordinal for c in db.scalars(select(Chunk).where(Chunk.document_id == doc.id))}
    for i, (text, vector) in enumerate(zip(parts, vectors)):
        if i not in existing:
            db.add(Chunk(workspace_id=doc.workspace_id, document_id=doc.id, ordinal=i,
                         text=text, embedding=vector, embedding_model=model_id()))
    doc.status = "ready"
    # Raw text is no longer needed after successful indexing.
    doc.content = ""


def tokens(text):
    words = re.findall(r"\b[a-z0-9]+\b", text.lower())
    return [w[:-1] if len(w) > 4 and w.endswith("s") and not w.endswith("ss") else w for w in words if w not in ENGLISH_STOP_WORDS]


def search(db, workspace_id, question, top_k=5):
    # Scope both chunks and document joins; never trust a workspace ID from a JWT alone.
    rows = db.execute(select(Chunk, Document.name).join(Document, Chunk.document_id == Document.id).where(
        Chunk.workspace_id == workspace_id, Document.workspace_id == workspace_id,
        Document.status == "ready", Chunk.embedding_model == model_id())).all()
    if not rows:
        return []
    query = np.array(embed([question])[0])
    corpus = [Counter(tokens(c.text)) for c, _ in rows]
    q = set(tokens(question))
    n = len(rows)
    avg_len = sum(sum(c.values()) for c in corpus) / n or 1
    document_frequency = Counter(term for counts in corpus for term in counts)
    similarities = np.asarray([chunk.embedding for chunk, _ in rows]) @ query
    sparse = []
    dense = []
    for i, ((chunk, _), counts) in enumerate(zip(rows, corpus)):
        length = sum(counts.values())
        score = 0.0
        for term in q:
            freq = counts[term]
            df = document_frequency[term]
            idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
            score += idf * freq * 2.5 / (freq + 1.5 * (0.25 + 0.75 * length / avg_len)) if freq else 0
        sparse.append((i, score))
        dense.append((i, float(similarities[i])))
    # Exact candidate retrieval is deliberately bounded by workspace chunk quota.
    ranks = {}
    for candidates in (sorted(sparse, key=lambda x: x[1], reverse=True), sorted(dense, key=lambda x: x[1], reverse=True)):
        for rank, (i, score) in enumerate(candidates):
            if score > 0:
                ranks[i] = ranks.get(i, 0) + 1 / (60 + rank + 1)
    output = []
    for i, score in sorted(ranks.items(), key=lambda x: x[1], reverse=True)[:top_k]:
        c, name = rows[i]
        # Hash collisions alone must not qualify as evidence in hashing mode.
        if get_settings().embedding_mode == "hashing" and not q.intersection(corpus[i]):
            continue
        output.append({"chunk_id": c.id, "document_id": c.document_id, "name": name,
                       "text": c.text, "ordinal": c.ordinal, "score": round(score, 6)})
    return output

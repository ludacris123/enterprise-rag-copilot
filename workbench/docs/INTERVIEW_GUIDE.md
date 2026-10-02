# Explain the project in an AI engineering interview

## A truthful short introduction

“I built a React and FastAPI workspace where users can upload documents, ask grounded questions, run bounded AI tools, and evaluate responses against golden cases. I implemented real account verification and password recovery, revocable JWT sessions, workspace roles, Alembic-managed persistence, and Celery background jobs. Groq/OpenAI adapters provide live generation, while an explicitly labeled extractive baseline lets reviewers run it without keys. I added input/output guardrails, retrieval and answer metrics, trace history, an approval step for writes, scikit-learn experiments, and a CUDA quantization benchmark script.”

Use “I measured” only for measurements you personally run. Do not say this was deployed to customers, scaled to millions of requests, or demonstrated a particular GPU speedup without evidence.

## Decisions worth discussing

1. **Why a durable DB job before queue dispatch?** An acknowledged request survives a Redis outage. The scheduler can retry dispatch. Delivery is at least once, so the claim/side-effect path must be idempotent.
2. **Why aren't tenant roles in the JWT authoritative?** A role can change while a token remains valid. The DB session and current membership must still permit the request.
3. **Why rotate refresh tokens?** A replay of a used token revokes the session. Password reset revokes all sessions. Hashes limit exposure if the DB leaks.
4. **Why an offline baseline?** It makes the application reviewable without an API key and offers a reproducible comparison. It is an extractive/lexical baseline, not simulated model intelligence.
5. **Why RRF?** Dense and BM25 scores have different scales. Rank fusion avoids comparing them directly. Tune the candidate set and evaluate Recall@K before adding complex rerankers.
6. **Why separate approval from the graph?** Read-only nodes can be retried; a persisted proposed write requires an authorized transaction and a unique constraint.
7. **What does citation validity mean?** It checks that citations refer to retrieved chunks. It does not prove the answer follows logically from those chunks. Human/LLM grading and adversarial datasets are additional layers.
8. **Why split before preprocessing in ML?** Fitting imputation/scaling on the entire dataset leaks holdout information. A Pipeline fits only on the training partition.
9. **What does quantization change?** It trades weight precision/memory for potential quality and runtime differences. Compare peak memory and throughput on fixed hardware, and evaluate outputs separately.
10. **What would you change for larger workloads?** ANN retrieval with tenant filters, object storage, per-case evaluation fan-out, model governance, richer agent checkpoints, and explicit token budgets—after profiling the bottleneck.

## A five-minute demo

- Register/verify/login and show that a viewer cannot upload or run models.
- Upload the sample policy and ask the refund question. Open the evidence cards.
- Submit an instruction-override prompt and show the blocked run.
- Run an agent that proposes a note, then approve it and show the audit entry.
- Run the golden dataset and explain Recall@5/MRR versus lexical answer quality.
- Train the sample CSV baseline, inspect the confusion matrix, then predict.
- Show traces with provider tokens and latency. Show quantization results only if you have measured them on your GPU.

## Be ready to explain limitations

The default embeddings are feature hashes. Exact JSON-vector search is intentionally capped. Safety checks are heuristic. There is no implemented ANN index, cross-encoder, enterprise SSO, subscription billing, arbitrary autonomous agent toolset, or production traffic claim. Showing a clear boundary and a measured improvement plan is stronger than claiming features that are only architectural ideas.

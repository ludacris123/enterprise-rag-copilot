# AI Engineering Workbench

A runnable SaaS-style portfolio application for RAG, bounded agents, evaluation, guardrails, ML experiments, and model observability. Built with **React + TypeScript, FastAPI, SQLAlchemy, Alembic, PostgreSQL, Redis, Celery, LangGraph, and scikit-learn**.

This directory is a complete new application alongside the original repository's reference copilot. Run commands from `workbench/`; the repository-root Compose file runs the older app.

## Run

```bash
cd workbench
cp .env.example .env
docker compose up --build
```

Open **http://localhost:5173**. Create an account, open its verification link in the development inbox at **http://localhost:8025**, then sign in. See [deployment instructions](docs/DEPLOYMENT.md) for Windows, non-Docker setup, API keys, and deployment.

## Implemented features

| Area | Working behavior |
|---|---|
| Accounts | Signup, email verification/resend, login/logout, Argon2id hashing, forgot/reset/change password, session listing/revocation |
| Sessions | Short-lived JWT, HttpOnly refresh cookie, rotation/reuse detection, immediate revocation, origin checks |
| Workspaces | Membership checks on every route; owner/admin/member/viewer; team management; workspace creation |
| Persistence | Alembic migrations; SQLAlchemy/PostgreSQL; persistent documents, chunks, jobs, datasets, notes, traces, audit events |
| RAG | Text PDF/TXT/Markdown upload, validation/deduplication, overlap chunks, BM25/vector retrieval, RRF, source citations, missing-evidence refusal |
| Providers | Real Groq/OpenAI adapters, optional operator-configured local server, labeled offline extractive baseline |
| Agents | LangGraph tool selection, read-only knowledge/stats tools, guarded execution, persisted note proposal, owner/admin approval |
| Evaluations | Golden-case editor, token F1, phrase matching, Recall@5, MRR, safety/refusal checks, advisory LLM judge, JSON export |
| Guardrails | Instruction-override pattern checks, email/phone/key redaction, output citation validation, role checks, tenant scope |
| ML | CSV classification/regression, leakage-aware preprocessing, logistic/Ridge/random-forest baselines, holdout reports, prediction API/UI |
| Model lab | Import/export measured FP16/INT8/NF4 reports; actual CUDA benchmark script included |
| Operations | Durable job outbox, retries/timeouts/recovery, SMTP outbox, Redis rate limits, quotas, request IDs, Prometheus, readiness/liveness |
| Delivery | Docker Compose, Nginx production build, dependency locks, CI, tests, architecture and interview guides |

The default vector adapter uses feature hashing, not semantic embeddings. A real sentence-transformer adapter is optional. Exact vector retrieval is capped at 5,000 chunks per workspace; pgvector/ANN is a documented scaling path, not an implemented feature. Heuristic guardrails and citation checks do not guarantee factual correctness. This version does not implement subscription billing or enterprise SSO.

## Review a complete flow

1. Verify an account and upload the provided sample policy through Knowledge.
2. Ask the refund question in RAG workspace and inspect source cards.
3. Switch to Agent runs, propose a note, and approve/reject it.
4. Save the starter evaluation cases and run the suite.
5. Train the synthetic sample CSV and make predictions.
6. Export traces/reports. Add a verified viewer and test read-only access.

Groq/OpenAI keys belong only in the server environment. Groq free quotas and model availability depend on your account. The UI disables unconfigured providers; it never silently substitutes offline output for a failed live model.

## Source map

```text
backend/app/       auth, persistence, APIs, pipelines, worker, ML
backend/alembic/   frozen migration revisions
backend/tests/     account/security/AI/ML regressions
frontend/src/      React workspace and account flows
scripts/          quality gate and CUDA quantization benchmark
docs/             architecture, deployment, validation, interview guide
compose.yaml      local service stack
```

- [Architecture and system design](docs/ARCHITECTURE.md)
- [Setup and deployment](docs/DEPLOYMENT.md)
- [Actual validation results](docs/VALIDATION.md)
- [Interview explanation and demo](docs/INTERVIEW_GUIDE.md)

## Tests

```bash
cd backend
pip install -r requirements.lock
pip install -e '.[dev]' --no-deps
pytest -q
alembic upgrade head
alembic check
cd ../frontend
npm ci
npm run build
```

API documentation is available at `/docs` on the backend. GPU quantization and live provider calls require separate credentials/hardware and are not represented as verified by offline tests.

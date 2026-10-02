# Running and deploying Workbench

## Local Docker setup

From the repository root:

```bash
cd workbench
cp .env.example .env
docker compose up --build
```

On Windows PowerShell replace `cp` with `Copy-Item`. Install Docker Desktop with its WSL2 backend first.

- Application: http://localhost:5173
- Development email inbox (Mailpit): http://localhost:8025
- API documentation: http://localhost:8000/docs

Sign up in the application. Open the verification email in Mailpit and click its link. Sign in afterward. Verification is required; there is no built-in administrator password or bypass.

Compose launches PostgreSQL, Redis, the Alembic migration service, FastAPI, a Celery worker/scheduler, Nginx/React, and Mailpit. Data persists in named volumes. `docker compose down` preserves data; `docker compose down -v` deletes it.

### Configure real providers

Set `GROQ_API_KEY` and/or `OPENAI_API_KEY` in `.env`. Keep the file out of Git. Set the model name to one currently available to your account. Free-tier availability and quotas can change; the application handles errors but cannot guarantee free usage. Model IDs in `.env.example` are configurable starting points.

```bash
docker compose up -d --force-recreate api worker scheduler
```

Groq/OpenAI become enabled in the provider selector after the backend restarts and you reload the page. Keys are never returned to the browser. OpenAI may require paid credits. Do not paste keys into uploaded documents or commit them.

### Try a complete flow

1. Register, open Mailpit, verify, and sign in.
2. Download the sample support policy from Knowledge; upload it and wait for `ready`.
3. Ask “What is the refund window?” in RAG workspace. Inspect evidence IDs and source excerpts.
4. Run the same question in Agent runs with “Propose saving a note”. Review and approve it as owner/admin.
5. Save the default evaluation cases. Add the document ID to the first case's `expected_document_ids` to measure Recall@5/MRR. Run offline first, then repeat with Groq/OpenAI to compare actual behavior.
6. Download the synthetic sample CSV in ML experiments; upload it with target `target`. Inspect metrics. Predict with `[{"length": 8, "width": 3}]`.
7. Inspect/export traces and evaluation reports. Add a verified teammate as viewer to test read-only permissions.
8. Use Forgot password and follow the reset email. Confirm that old sessions can no longer access the workspace.

## Without Docker

Requires Python 3.12+, Node 22+, Redis, and an SMTP server such as Mailpit. Use PostgreSQL for concurrent workloads; SQLite supports local single-process evaluation.

```bash
cd workbench/backend
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell instead:
# .venv\Scripts\Activate.ps1
pip install -r requirements.lock
pip install -e . --no-deps
alembic upgrade head
uvicorn app.main:app --reload
```

In two other terminals, from `workbench/backend` with the same environment:

```bash
celery -A app.worker.celery worker --loglevel=INFO --pool=solo
celery -A app.worker.celery beat --loglevel=INFO
```

The solo pool is convenient for Windows/local development. Use a Linux prefork worker in production. The gateway needs the worker and scheduler to complete jobs and send emails. It never starts them automatically.

```bash
cd workbench/frontend
npm ci
npm run dev
```

The Vite proxy forwards `/api` to `127.0.0.1:8000`. Default local settings point to Redis `localhost:6379` and SMTP `localhost:1025`. If using `.env`, place it in the backend working directory for non-Docker commands; `.env.example`'s Compose service hostnames must be replaced with localhost, and `ARTIFACT_DIR` set to `./artifacts`.

## Semantic embeddings

In a local backend environment, install `pip install -e '.[semantic]'`. Set `EMBEDDING_MODE=semantic` and optionally `EMBEDDING_MODEL`. Remove and re-upload documents to recreate their vectors. For Docker, build a backend image including this extra and restart the API/worker; the baseline image intentionally avoids downloading a transformer model. Mount a persistent model cache for repeated deployments.

## Quantization

Install the optional environment on a compatible NVIDIA CUDA GPU; verify that Torch sees your GPU before running. Choose a model that fits fully on one GPU in FP16, and check its license/access conditions.

```bash
cd workbench/backend
pip install -e '.[quantization]'
cd ..
python scripts/benchmark_quantization.py --model Qwen/Qwen2.5-0.5B-Instruct --output benchmark-output/report.json
```

Import `benchmark-output/report.json` in Model lab. The benchmark's numbers are actual measurements from the machine running it. This source deliverable includes no fabricated benchmark report.

For local chat generation, separately serve your model with an OpenAI-compatible inference server. Set `ENABLE_LOCAL_MODEL=true`, `LOCAL_MODEL_URL`, and `LOCAL_MODEL_NAME`. The benchmark itself is not an inference server, and a bitsandbytes checkpoint is not automatically a GGUF model. Docker workers can reach an operator's local inference server through `host.docker.internal` when its bind address allows it.

## Production deployment

Deploy the container stack to a Linux host or container platform that supports Python workers. GitHub stores source; it does not run this Python backend. A static frontend host alone is insufficient.

Use a single HTTPS origin with `/api` proxied to FastAPI. Set:

- `APP_ENV=production`
- a unique random `JWT_SECRET` of at least 32 characters
- `COOKIE_SECURE=true`
- `FRONTEND_URL=https://your-domain.example` (exact origin, no trailing slash)
- a PostgreSQL `DATABASE_URL` with TLS as required by the provider
- reachable Redis and a real SMTP service with credentials/TLS
- persistent artifact storage, DB backups, restricted operator access, and monitoring

The app rejects development secrets, insecure cookies, SQLite, and eager jobs in production. The Compose template binds the frontend/API/Mailpit to localhost for local development. Put your TLS ingress in front of the frontend or deliberately change the frontend binding after configuring network controls. Keep PostgreSQL/Redis/Mailpit/API ports private. Restrict `/metrics` and optionally `/docs` to operators at the gateway.

Use one scheduler, independently scalable workers, and controlled migrations. Take backups before migrations. The `downgrade base` command deletes tables; it is a test/reset operation, not a safe rollback for real user data.

### Data retention

Raw document content is cleared after successful ingestion, and training CSV text after completion/failure. Chunks, run answers, evaluation cases, approved notes, and trace metadata remain in PostgreSQL. Password reset invalidates sessions but does not delete workspace data. Implement a scheduled retention/deletion policy and backup expiration before handling real customer data. Protect the artifact volume: joblib loading trusts files created by the server, so its integrity matters.

## Troubleshooting

| Symptom | Check |
|---|---|
| Verification email absent | Scheduler/worker running; SMTP configured; Mailpit inbox; `email_outbox` failed status |
| Job stays queued | Redis, Celery worker, scheduler, queued-job age |
| Provider disabled | Server environment variables; recreate backend services; reload browser |
| Provider HTTP error | Current model availability, key scope, account quota; inspect job's sanitized error |
| No evidence after changing embeddings | Remove/reindex documents with the new embedding model |
| Forbidden refresh | Exact frontend origin and HTTPS/cookie settings; avoid mixing localhost and 127.0.0.1 |
| Model prediction artifact unavailable | Shared artifact volume present on API and worker |
| Quantization fails | Compatible CUDA, sufficient VRAM, pinned compatible library versions, model access |

## Validation

```bash
cd workbench/backend
pytest -q
alembic check
cd ../frontend
npm run build
```

CI also checks migrations on PostgreSQL. Optional live-provider/GPU tests incur external dependencies and are not included in the offline test gate. See `VALIDATION.md` for what was actually run for this delivery.

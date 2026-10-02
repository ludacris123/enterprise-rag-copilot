# Validation record

This record separates checks performed for this delivery from integrations that require additional credentials or infrastructure.

## Passed locally

- **29 backend tests**: account verification, Argon2id hashing, authentication, refresh rotation/reuse detection, cookie-origin checks, logout/password-reset session revocation, expired/single-use recovery links, password change, login throttling, session revocation, tenant isolation, viewer permissions, persistent citations/PII redaction, invalid/duplicate uploads, injection/refusal checks, idempotent agent approval, agent stats, evaluation metrics, provider HTTP contract with a stub, missing provider configuration, quotas, ML classification/regression/prediction, duplicate worker delivery, quantization-report validation, and document deletion.
- **Alembic**: upgrade to head, schema-drift check, downgrade to base, and upgrade again on SQLite.
- **React**: strict TypeScript compilation and optimized Vite production build.
- **GitHub Actions**: backend tests/migrations, PostgreSQL migrations and backend tests, frontend build, Docker Compose configuration, and backend/frontend image builds passed for the initial Workbench commit.
- **Source/configuration**: Python source compilation, YAML structure checks, frozen initial migration, frontend lockfile, backend requirements lock.

## Live integration

A local smoke stack used real HTTP, Redis, a Celery worker/scheduler, an SMTP capture server, and SQLite. It exercised persisted asynchronous document ingestion, RAG queries, note approval, evaluations, ML training/prediction, refresh/logout, and verification/reset mail delivery. This is a development integration check; it is not a PostgreSQL load test.

## Browser and full-stack checks passed in GitHub Actions

Workbench CI passed all five jobs: backend, PostgreSQL, frontend, containers, and browser. The Playwright test ran against the real Docker Compose stack and exercised login, document ingestion, RAG citations, persisted history after reload, agent note approval, evaluations, ML training/prediction, observability, audit history, and logout. All eight application pages passed horizontal-overflow checks at 390, 768, and 1440 pixels.

Evidence: [Workbench CI run](https://github.com/ludacris123/enterprise-rag-copilot/actions/runs/37038236799), tested implementation commit `b4db3e0e236977c19bbbe091f198abe3bbfba90d`.

The repository's separate legacy CI workflow still has failures in the unchanged root reference application. This delivery remains on the feature branch and PR rather than replacing the root application.

## Not verified in this environment
- **Local PostgreSQL/container runtime**: unavailable locally. The equivalent PostgreSQL/backend and container-build checks passed in GitHub Actions. No production load test was performed.
- **Live Groq/OpenAI calls**: no user API keys were supplied. Adapter contracts were tested with controlled responses; actual account/model availability and quota are external requirements.
- **Semantic transformer embeddings**: the baseline hashing adapter was exercised. Optional sentence-transformer model download/runtime was not tested.
- **CUDA quantization**: no compatible GPU was available. The benchmark source and report schema are implemented; no speedup, VRAM reduction, or quality score is claimed.
- **Production SMTP/TLS/domain hosting**: development SMTP was exercised; real email delivery and HTTPS ingress must be configured.

Do not describe this application as production-audited, load-tested, or deployed to customers. Review the architecture's implementation boundaries before presenting it in an interview.

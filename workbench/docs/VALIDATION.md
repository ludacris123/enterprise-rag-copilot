# Validation record

This record separates checks performed for this delivery from integrations that require additional credentials or infrastructure.

## Passed locally

- **29 backend tests**: account verification, Argon2id hashing, authentication, refresh rotation/reuse detection, cookie-origin checks, logout/password-reset session revocation, expired/single-use recovery links, password change, login throttling, session revocation, tenant isolation, viewer permissions, persistent citations/PII redaction, invalid/duplicate uploads, injection/refusal checks, idempotent agent approval, agent stats, evaluation metrics, provider HTTP contract with a stub, missing provider configuration, quotas, ML classification/regression/prediction, duplicate worker delivery, quantization-report validation, and document deletion.
- **Alembic**: upgrade to head, schema-drift check, downgrade to base, and upgrade again on SQLite.
- **React**: strict TypeScript compilation and optimized Vite production build.
- **Source/configuration**: Python source compilation, YAML structure checks, frozen initial migration, frontend lockfile, backend requirements lock.

## Live integration

A local smoke stack used real HTTP, Redis, a Celery worker/scheduler, an SMTP capture server, and SQLite. It exercised persisted asynchronous document ingestion, RAG queries, note approval, evaluations, ML training/prediction, refresh/logout, and verification/reset mail delivery. This is a development integration check; it is not a PostgreSQL load test.

## Not verified in this environment

- **Browser visual/interaction QA**: a headless Chromium runtime could not start under this environment's runtime constraints. No claim is made that desktop/mobile screenshots were reviewed. The responsive source and build are present; check rendering in your browser before a public deployment.
- **PostgreSQL/container runtime**: local PostgreSQL/container processes were unavailable. GitHub Actions includes PostgreSQL migration/backend tests and Docker Compose configuration/image-build jobs; those results must be checked separately.
- **Live Groq/OpenAI calls**: no user API keys were supplied. Adapter contracts were tested with controlled responses; actual account/model availability and quota are external requirements.
- **Semantic transformer embeddings**: the baseline hashing adapter was exercised. Optional sentence-transformer model download/runtime was not tested.
- **CUDA quantization**: no compatible GPU was available. The benchmark source and report schema are implemented; no speedup, VRAM reduction, or quality score is claimed.
- **Production SMTP/TLS/domain hosting**: development SMTP was exercised; real email delivery and HTTPS ingress must be configured.

Do not describe this application as production-audited, load-tested, or deployed to customers. Review the architecture's implementation boundaries before presenting it in an interview.

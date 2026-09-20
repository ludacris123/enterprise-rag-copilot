.PHONY: dev test eval lint
dev:
	docker compose up --build
test:
	cd backend && python -m pytest -q
eval:
	cd backend && python -m evals.run
lint:
	cd backend && python -m ruff check .
	cd frontend && npm run build

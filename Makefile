SHELL := /bin/zsh
PY := backend/.venv/bin/python
PNPM_HOME ?= $(HOME)/Library/pnpm
PNPM := $(PNPM_HOME)/pnpm

.PHONY: up install migrate seed api web check eval fixtures ingest ingest-watch accept demo-reset

up:
	docker compose up -d --wait

install:
	python3.12 -m venv backend/.venv
	backend/.venv/bin/pip install --upgrade pip -q
	backend/.venv/bin/pip install -r backend/requirements.txt
	cd frontend && $(PNPM) install

migrate:
	cd backend && .venv/bin/alembic upgrade head

seed:
	cd backend && .venv/bin/python -m scripts.seed

api:
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

web:
	cd frontend && $(PNPM) dev

check:
	cd backend && .venv/bin/pytest -q tests && .venv/bin/python -m scripts.smoke && .venv/bin/python -m scripts.smoke_epic5

eval:
	cd backend && .venv/bin/python -m scripts.evaluate

fixtures:
	cd backend && .venv/bin/python -m scripts.gen_fixtures

# Poll the configured feeds once. Safe to repeat: duplicates are skipped.
ingest:
	cd backend && .venv/bin/python -m scripts.ingest_feeds

ingest-watch:
	cd backend && .venv/bin/python -m scripts.ingest_feeds --watch

# Does it give the RIGHT answer, case by case? Needs the API running.
accept:
	cd backend && .venv/bin/python -m scripts.acceptance

demo-reset:
	cd backend && .venv/bin/alembic downgrade base && .venv/bin/alembic upgrade head && .venv/bin/python -m scripts.gen_fixtures && .venv/bin/python -m scripts.seed && .venv/bin/python -m scripts.ingest_feeds --quiet

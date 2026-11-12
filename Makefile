SHELL := /bin/bash

.PHONY: install local-up local-down api-test lint typecheck security test coverage build seed check-invgate

install:
	pip install -r requirements.txt -r requirements-dev.txt

local-up:
	uvicorn backend.server:app --host 0.0.0.0 --port $${PORT:-8000} --reload

local-down:
	@echo "Detenido (Ctrl+C)."

api-test:
	@echo "Healthcheck:"
	curl -s http://127.0.0.1:$${PORT:-8000}/api/health

lint:
	ruff check backend tests scripts
	ruff format --check backend tests scripts

typecheck:
	mypy --explicit-package-bases backend

security:
	bandit -q -r backend scripts

test:
	pytest --cov=backend --cov=scripts --cov-report=term-missing

coverage:
	pytest --cov=backend --cov=scripts --cov-report=term-missing --cov-fail-under=90.01

build:
	docker build -t valkiria-invgate:local .

# Puebla el dashboard con N conversaciones de demo (por defecto 40)
seed:
	python -m scripts.seed_demo_telemetry -n $${N:-40}

# Prueba de humo contra InvGate real. Ejemplo: make check-invgate ARGS="--incident 123"
check-invgate:
	python -m scripts.check_invgate $${ARGS:-}

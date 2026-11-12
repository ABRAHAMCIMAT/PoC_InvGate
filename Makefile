SHELL := /bin/bash

.PHONY: install lock local-up local-down api-test lint typecheck security test coverage build seed check-invgate

install:
	pip install --require-hashes --only-binary :all: -r requirements-dev.lock

# Regenera los locks con hashes (Linux, Python 3.15; Bandit en 3.13). Requiere uv.
LOCK_OPTS = --python-platform x86_64-manylinux_2_28 --only-binary :all: --generate-hashes --no-header -q
lock:
	uv pip compile requirements.txt --python-version 3.15 $(LOCK_OPTS) -o requirements.lock
	uv pip compile requirements-dev.txt --python-version 3.15 $(LOCK_OPTS) -o requirements-dev.lock
	uv pip compile requirements-security.txt --python-version 3.13 $(LOCK_OPTS) -o requirements-security.lock

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
	bandit -q -r backend scripts -x tests

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

SHELL := /bin/bash

.PHONY: install local-up local-down api-test lint typecheck test coverage build

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
	mypy backend

test:
	pytest --cov=backend --cov-report=term-missing

coverage:
	pytest --cov=backend --cov-report=term-missing --cov-fail-under=90.01

build:
	docker build -t valkiria-invgate:local .

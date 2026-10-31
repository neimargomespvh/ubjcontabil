.PHONY: help install test lint typecheck docker-up docker-down migrate clean

help:
	@echo "Targets: install test lint typecheck docker-up docker-down migrate clean"

install:
	pip install -r requirements.txt

test:
	pytest -v --tb=short

test-cov:
	pytest -v --cov=src --cov-report=term-missing

lint:
	ruff check src/ tests/ scripts/

typecheck:
	mypy src/

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

migrate:
	@if [ -z "$$ERP_DATABASE_URL" ]; then echo "Defina ERP_DATABASE_URL"; exit 1; fi
	psql "$$ERP_DATABASE_URL" -f ddl/init.sql

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage htmlcov

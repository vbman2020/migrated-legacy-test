.PHONY: help install dev test lint format clean docker-build docker-up docker-down migrate

help:
	@echo "Available commands:"
	@echo "  make install      - Install dependencies"
	@echo "  make dev          - Run development server"
	@echo "  make test         - Run tests with coverage"
	@echo "  make lint         - Run linters (ruff, black, isort)"
	@echo "  make format       - Format code with black and isort"
	@echo "  make clean        - Clean cache and build files"
	@echo "  make docker-build - Build Docker images"
	@echo "  make docker-up    - Start Docker containers"
	@echo "  make docker-down  - Stop Docker containers"
	@echo "  make migrate      - Run database migrations"
	@echo "  make migration    - Create new migration (use MSG='description')"

install:
	pip install --upgrade pip
	pip install -r requirements.txt

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest tests/ -v --cov=app --cov-report=term-missing --cov-report=html

lint:
	ruff check app/ tests/
	black --check app/ tests/
	isort --check-only app/ tests/
	mypy app/

format:
	black app/ tests/
	isort app/ tests/
	ruff check app/ tests/ --fix

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/ .coverage coverage.xml

docker-build:
	docker-compose build

docker-up:
	docker-compose up -d
	@echo "Waiting for services to be ready..."
	@sleep 5
	@echo "Application available at http://localhost:8000"
	@echo "API docs available at http://localhost:8000/docs"

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f app

migrate:
	alembic upgrade head

migration:
	@if [ -z "$(MSG)" ]; then \
		echo "Error: Please provide a migration message using MSG='description'"; \
		exit 1; \
	fi
	alembic revision --autogenerate -m "$(MSG)"

db-shell:
	docker-compose exec db psql -U realworld -d realworld_db

shell:
	docker-compose exec app /bin/sh
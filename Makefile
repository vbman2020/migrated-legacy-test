# Makefile for Conduit API

.PHONY: help install dev-install test lint format clean docker-build docker-up docker-down migrate db-upgrade db-downgrade

# Default target
.DEFAULT_GOAL := help

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install production dependencies
	pip install -r requirements.txt

dev-install: ## Install development dependencies
	pip install -r requirements.txt
	pre-commit install

test: ## Run tests with coverage
	pytest tests/ -v --cov=app --cov-report=term-missing --cov-report=html

test-unit: ## Run unit tests only
	pytest tests/ -v -m unit

test-integration: ## Run integration tests only
	pytest tests/ -v -m integration

lint: ## Run linters (ruff, black, isort, mypy)
	@echo "Running ruff..."
	ruff check app/ tests/
	@echo "Running black..."
	black --check app/ tests/
	@echo "Running isort..."
	isort --check-only app/ tests/
	@echo "Running mypy..."
	mypy app/ --ignore-missing-imports

format: ## Format code with black and isort
	black app/ tests/
	isort app/ tests/
	lint-fix: ## Auto-fix linting issues
	ruff check --fix app/ tests/
	black app/ tests/
	isort app/ tests/

security: ## Run security checks
	safety check
	bandit -r app/

clean: ## Clean up generated files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .coverage htmlcov .mypy_cache .ruff_cache

docker-build: ## Build Docker image
	docker-compose build

docker-up: ## Start all services
	docker-compose up -d

docker-down: ## Stop all services
	docker-compose down

docker-logs: ## View logs from all services
	docker-compose logs -f

docker-clean: ## Remove all containers, volumes, and images
	docker-compose down -v --rmi all

migrate: ## Create a new migration
	@read -p "Enter migration message: " msg; \
	alembic revision --autogenerate -m "$$msg"

db-upgrade: ## Run database migrations
	alembic upgrade head

db-downgrade: ## Rollback last migration
	alembic downgrade -1

db-reset: ## Reset database (WARNING: destroys all data)
	alembic downgrade base
	alembic upgrade head

run: ## Run development server
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run-prod: ## Run production server
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

shell: ## Open Python shell with app context
	python -i -c "from app.main import app; from app.database import SessionLocal"

cov-report: ## Open coverage report in browser
	python -m webbrowser htmlcov/index.html

check: lint test ## Run all checks (lint + test)

ci: lint test security ## Run CI pipeline locally
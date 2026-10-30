# ContextKeeper Makefile

.PHONY: install run seed reset test lint docker help

PYTHON = python
PIP = pip
UVICORN = uvicorn

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## Install all dependencies
	$(PIP) install -r requirements.txt

run:  ## Start the development server
	$(UVICORN) app.main:app --reload --host 0.0.0.0 --port 8000

run-prod:  ## Start production server
	$(UVICORN) app.main:app --host 0.0.0.0 --port 8000 --workers 2

seed:  ## Seed the database with realistic sample data
	$(PYTHON) -m app.seed

reset:  ## Wipe the database and reseed
	-rm -f contextkeeper.db
	-rm -rf logs/*.log
	$(PYTHON) -m app.seed

migrate:  ## Run Alembic migrations
	alembic upgrade head

migrate-init:  ## Initialize Alembic migrations
	alembic init migrations

test:  ## Run all tests
	$(PYTHON) -m pytest tests/ -v --tb=short

test-cov:  ## Run tests with coverage report
	$(PYTHON) -m pytest tests/ -v --tb=short --cov=app --cov-report=term-missing

lint:  ## Run ruff linter
	ruff check app/ tests/

lint-fix:  ## Run ruff with auto-fix
	ruff check --fix app/ tests/

format:  ## Format code with ruff
	ruff format app/ tests/

docker:  ## Build Docker image
	docker build -t contextkeeper:latest .

docker-up:  ## Start with docker-compose
	docker-compose up --build

docker-down:  ## Stop docker-compose
	docker-compose down

clean:  ## Clean up pyc files and caches
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -delete
	find . -type d -name ".ruff_cache" -delete


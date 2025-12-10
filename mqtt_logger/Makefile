.PHONY: help install test test-cov lint format clean run

help:  ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies
	uv sync --all-extras

test:  ## Run tests
	uv run pytest -v

test-cov:  ## Run tests with coverage
	uv run pytest --cov=src --cov-report=html --cov-report=term

lint:  ## Run linting checks
	uv run ruff check src tests

format:  ## Format code
	uv run ruff format src tests
	uv run ruff check --fix src tests

clean:  ## Clean build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete
	find . -type f -name '*.pyo' -delete
	find . -type d -name '*.egg-info' -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .coverage htmlcov dist build

run:  ## Run the application
	uv run python main.py config/mqtt_logger.toml

dev:  ## Run in development mode with debug logging
	@echo "[mqtt]\nbroker = \"test.mosquitto.org\"\nport = 1883\n\n[database]\npath = \"data/dev.db\"\n\n[[topics]]\npattern = \"test/#\"\ntable_name = \"test_messages\"\n\n[logging]\nlevel = \"DEBUG\"" > config/dev.toml
	uv run python main.py config/dev.toml

docker-build:  ## Build Docker image
	./build-docker.sh

docker-run:  ## Run Docker container
	./run-docker.sh

docker-logs:  ## View Docker logs
	docker logs -f mqtt-logger

docker-stop:  ## Stop Docker container
	docker stop mqtt-logger

docker-clean:  ## Remove Docker container and image
	docker stop mqtt-logger 2>/dev/null || true
	docker rm mqtt-logger 2>/dev/null || true
	docker rmi mqtt-logger:latest 2>/dev/null || true


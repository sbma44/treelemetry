.PHONY: help install build test deploy clean sample-data

help: ## Show this help message
	@echo "Treelemetry - Christmas Tree Water Level Monitor"
	@echo ""
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install all dependencies
	@echo "Installing mqtt_logger dependencies..."
	cd mqtt_logger && uv sync
	@echo "Installing infrastructure dependencies..."
	cd infrastructure && uv sync
	@echo "Installing uploader dependencies..."
	cd uploader && uv sync
	@echo "Installing site dependencies..."
	cd site && npm install
	@echo "✓ All dependencies installed"

build-site: ## Build the static site
	@echo "Building static site..."
	cd site && npm run build
	@echo "✓ Site built to docs/"

build-docker-logger: ## Build MQTT Logger Docker image
	@echo "Building MQTT Logger Docker image..."
	cd mqtt_logger && docker build -t mqtt-logger .
	@echo "✓ MQTT Logger Docker image built"

build-docker-uploader: ## Build Uploader Docker image
	@echo "Building Uploader Docker image..."
	cd uploader && docker build -t treelemetry-uploader .
	@echo "✓ Uploader Docker image built"

build-docker: build-docker-logger build-docker-uploader ## Build all Docker images

build: build-site build-docker ## Build everything

deploy-infra: ## Deploy AWS infrastructure
	@echo "Deploying infrastructure..."
	cd infrastructure && npx aws-cdk deploy
	@echo "✓ Infrastructure deployed"

deploy-site: build-site ## Build and deploy the site
	@echo "Site built to docs/. Commit and push to deploy to GitHub Pages:"
	@echo "  git add docs && git commit -m 'Deploy site' && git push"

sample-data: ## Generate sample DuckDB data
	@echo "Generating sample data..."
	cd uploader && uv sync && uv run python sample_data.py ../tree.duckdb 1
	@echo "✓ Sample data created: tree.duckdb"

test-logger: ## Run MQTT Logger tests
	@echo "Running MQTT Logger tests..."
	cd mqtt_logger && uv run pytest
	@echo "✓ Tests passed"

test-logger-coverage: ## Run MQTT Logger tests with coverage
	@echo "Running MQTT Logger tests with coverage..."
	cd mqtt_logger && uv run pytest --cov=src --cov-report=html
	@echo "✓ Coverage report generated in mqtt_logger/htmlcov/"

test-uploader: ## Test the uploader locally
	@echo "Testing uploader (requires .env configuration)..."
	cd uploader && uv run python src/uploader.py

test: test-logger ## Run all tests

dev-site: ## Run site in development mode
	cd site && npm run dev

logs-logger: ## View MQTT Logger logs
	@docker logs -f mqtt-logger 2>/dev/null || echo "MQTT Logger container not running"

logs-uploader: ## View Uploader logs
	@docker logs -f treelemetry-uploader 2>/dev/null || echo "Uploader container not running"

clean: ## Clean build artifacts
	@echo "Cleaning build artifacts..."
	rm -rf site/node_modules
	rm -rf docs/*
	rm -rf infrastructure/cdk.out
	rm -rf uploader/.uv
	rm -rf mqtt_logger/.uv
	rm -rf mqtt_logger/.pytest_cache
	rm -rf mqtt_logger/htmlcov
	rm -f tree.duckdb
	@echo "✓ Clean complete"

docker-up: ## Start uploader with docker-compose
	docker-compose up -d

docker-down: ## Stop uploader
	docker-compose down

docker-logs: ## View uploader logs
	docker-compose logs -f

status: ## Check status of all components
	@echo "=== Treelemetry Status ==="
	@echo ""
	@echo "MQTT Logger:"
	@test -d mqtt_logger/src && echo "✓ Source code present" || echo "✗ Source missing"
	@docker images | grep -q mqtt-logger && echo "✓ Docker image built" || echo "○ Docker image not built"
	@docker ps | grep -q mqtt-logger && echo "✓ Container running" || echo "○ Container not running"
	@test -f mqtt_logger/data/mqtt_logs.db && echo "✓ Database exists" || echo "○ No database yet"
	@echo ""
	@echo "Infrastructure:"
	@cd infrastructure && npx aws-cdk list 2>/dev/null && echo "✓ CDK configured" || echo "✗ CDK not configured"
	@echo ""
	@echo "Uploader:"
	@test -f uploader/.env && echo "✓ .env exists" || echo "○ .env missing"
	@docker images | grep -q treelemetry-uploader && echo "✓ Docker image built" || echo "○ Docker image not built"
	@docker ps | grep -q treelemetry-uploader && echo "✓ Container running" || echo "○ Container not running"
	@echo ""
	@echo "Site:"
	@test -d site/node_modules && echo "✓ Dependencies installed" || echo "✗ Dependencies not installed"
	@test -f docs/index.html && echo "✓ Site built" || echo "✗ Site not built"
	@echo ""
	@echo "Data:"
	@test -f tree.duckdb && echo "✓ Sample DuckDB file exists" || echo "○ No sample file (use 'make sample-data')"


.PHONY: help install install-dev sync test test-unit test-e2e test-cov lint format type-check check clean run server coverage coverage-html pre-commit-install pre-commit-run

# Default target
help:
	@echo "Available targets:"
	@echo "  make install          - Install project dependencies"
	@echo "  make install-dev      - Install project with dev dependencies"
	@echo "  make sync             - Sync dependencies (uv sync --group dev)"
	@echo "  make test             - Run all unit tests (excluding e2e)"
	@echo "  make test-unit        - Run unit tests only"
	@echo "  make test-e2e         - Run e2e tests (loads vars from .env.e2e)"
	@echo "  make test-cov         - Run tests with coverage report"
	@echo "  make coverage         - Generate coverage report (terminal)"
	@echo "  make coverage-html    - Generate HTML coverage report"
	@echo "  make lint             - Run ruff linter"
	@echo "  make format           - Format code with ruff"
	@echo "  make type-check       - Run mypy type checker"
	@echo "  make check            - Run all quality checks (lint + format + type-check)"
	@echo "  make clean            - Clean build artifacts and cache"
	@echo "  make run              - Run the MCP CalDAV server"
	@echo "  make server           - Alias for 'run'"
	@echo "  make pre-commit-install - Install pre-commit hooks"
	@echo "  make pre-commit-run   - Run pre-commit on all files"

# Installation
install:
	uv sync

install-dev:
	uv sync --group dev

sync:
	uv sync --group dev

# Testing
test:
	uv run pytest tests/ -m "not e2e" -v

test-unit:
	uv run pytest tests/ -m "not e2e" -v

test-e2e:
	@if [ ! -f .env.e2e ]; then \
		echo "Error: .env.e2e file not found. Create it with CALDAV_URL, CALDAV_USERNAME, and CALDAV_PASSWORD"; \
		exit 1; \
	fi
	@zsh -c 'set -a && source .env.e2e && set +a && if [ -z "$$CALDAV_URL" ] || [ -z "$$CALDAV_USERNAME" ] || [ -z "$$CALDAV_PASSWORD" ]; then \
		echo "Error: E2E tests require CALDAV_URL, CALDAV_USERNAME, and CALDAV_PASSWORD in .env.e2e"; \
		exit 1; \
	fi && uv run pytest tests/e2e/ -v -m e2e'

test-cov:
	uv run pytest tests/ -m "not e2e" --cov=src/mcp_caldav --cov-report=term-missing --cov-report=html -v

coverage:
	uv run pytest tests/ -m "not e2e" --cov=src/mcp_caldav --cov-report=term-missing -v

coverage-html:
	uv run pytest tests/ -m "not e2e" --cov=src/mcp_caldav --cov-report=html -v
	@echo "Coverage report generated in htmlcov/index.html"

# Code quality
lint:
	uv run ruff check src/ tests/

format:
	uv run ruff format src/ tests/

format-check:
	uv run ruff format --check src/ tests/

type-check:
	uv run mypy src/mcp_caldav --ignore-missing-imports

check: lint format-check type-check
	@echo "All quality checks passed!"

# Pre-commit
pre-commit-install:
	uv run pre-commit install

pre-commit-run:
	uv run pre-commit run --all-files

# Running
run:
	uv run mcp-caldav

server: run

# Cleanup
clean:
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf htmlcov
	rm -rf dist
	rm -rf build
	rm -rf *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	@echo "Cleanup complete!"

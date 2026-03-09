.PHONY: install env dev test lint format clean

install:
	pip install -e ".[dev,lambda-pdf]"

env:
	cp -n .env.example .env
	@echo "Created .env from .env.example (mock mode enabled by default)"

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest -v

lint:
	ruff check .

format:
	ruff check --fix .
	ruff format .

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .ruff_cache

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Sumo Dashboard Viewer — ingests Sumo Logic scheduled report emails (PDF attachments), converts them to PNG images, and serves them via a mobile-friendly FastAPI web app with Google OAuth. Also exposes JSON API endpoints for programmatic access (e.g., canary health checks).

## Commands

```bash
make install      # Install project with dev + lambda-pdf dependencies
make dev          # Start uvicorn dev server with reload on :8000
make test         # Run all tests (pytest)
make lint         # Run ruff linter
make format       # Auto-fix and format with ruff
make env          # Create .env from .env.example with mock mode enabled
make clean        # Remove caches and build artifacts
```

Run a single test: `pytest tests/test_s3.py::test_name -v`

Requires Python 3.12+ and poppler (`brew install poppler` on macOS) for PDF conversion.

## Architecture

Three components sharing one repo:

1. **FastAPI web app** (`app/`) — serves dashboard images via browser (HTML/HTMX) and API (JSON)
2. **Lambda functions** (`lambda/`) — email processing pipeline (SES → parse email → extract PDF → convert to PNG → store in S3)
3. **CDK infrastructure** (`cdk/`) — single stack defining S3 buckets, Lambdas, ECS Fargate, CloudFront, SES

### Storage Abstraction

`app/s3/client.py` defines a `StorageClient` Protocol with two implementations:
- **S3StorageClient** — production, uses boto3 presigned URLs
- **LocalStorageClient** — mock mode, reads PNGs from `{MOCK_DATA_DIR}/dashboards/{slug}/{timestamp}.png` and serves via `/mock-static/`

The active implementation is set in `app/main.py` based on `MOCK_MODE` env var and stored on `app.state.storage`.

### Auth

Two auth paths enforced via FastAPI dependencies in `app/auth/dependencies.py`:
- **Browser routes** (`/`, `/dashboards/*`) — Google OAuth session via `require_google_session`
- **API routes** (`/api/v1/*`) — `X-API-Key` header via `require_api_key`, keys loaded from SSM Parameter Store

### Mock Mode

Set `MOCK_MODE=true` and `MOCK_AUTH=true` in `.env` for local development without AWS. Uses filesystem storage and bypasses OAuth. Example data ships in `example-data/dashboards/` (committed); real data can go in `mock-data/dashboards/` (gitignored).

### Lambda Pipeline

`email_processor` → parses MIME email, extracts PDF, derives dashboard slug from subject, invokes `pdf_converter` → converts PDF to PNG at 300 DPI, crops bottom whitespace, uploads to S3.

### S3 Key Convention

- PNGs: `dashboards/{dashboard-slug}/{YYYY-MM-DDTHH-MM-SSZ}.png`
- PDFs: `pdfs/{dashboard-slug}/{YYYY-MM-DDTHH-MM-SSZ}.pdf`
- Timestamp format uses hyphens instead of colons for S3 key safety

### Staleness

A dashboard snapshot is stale if older than `STALE_THRESHOLD_MINUTES` (default 30). Shown as amber warning in UI and `stale: true` in API responses.

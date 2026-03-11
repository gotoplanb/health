# Sumo Dashboard Viewer

Internal tool that ingests Sumo Logic scheduled report emails, converts PDF attachments to PNG images, and serves them via a mobile-friendly web app.

## Prerequisites

- Python 3.12+
- [poppler](https://poppler.freedesktop.org/) (for PDF conversion; `brew install poppler` on macOS, `apt install poppler-utils` on Debian/Ubuntu)

## Quick Start (Local Mock Mode)

Mock mode serves dashboard images from the local filesystem — no AWS required. Example data is included in the repo so you can see the app immediately.

```bash
# 1. Install dependencies
make install

# 2. Set up environment
make env

# 3. Start the dev server
make dev
```

The app runs at http://localhost:8000 with mock auth enabled by default. You'll see 4 example dashboards (Platform Overview, API Gateway, Payment Service, User Service) with 3 snapshots each.

## Example Data

The `example-data/` directory contains generated Sumo-style dashboard PNGs that ship with the repo. This is the default data source in mock mode.

To regenerate or customize the example dashboards:

```bash
pip install matplotlib numpy
python scripts/generate_example_data.py
```

## Custom Mock Data

To work with your own dashboard images, place PNGs in `mock-data/` and set `MOCK_DATA_DIR=mock-data` in `.env`:

```
mock-data/
  dashboards/
    my-first-dashboard/
      2026-01-01T07-00-00Z.png
      2026-01-01T06-45-00Z.png
    my-second-dashboard/
      2026-01-01T07-00-00Z.png
```

- Directory names are dashboard slugs (lowercase, hyphenated)
- Filenames are timestamps in `YYYY-MM-DDTHH-MM-SSZ` format
- To generate PNGs from Sumo PDF exports: `pdftoppm -r 300 -png dashboard.pdf output`
- `mock-data/` is gitignored — your real dashboard data stays local

## Makefile Targets

| Target | Description |
|---|---|
| `make install` | Install project with dev dependencies |
| `make env` | Create `.env` from `.env.example` with mock mode enabled |
| `make dev` | Start uvicorn dev server with reload |
| `make test` | Run all tests |
| `make lint` | Run ruff linter |
| `make format` | Auto-format with ruff |
| `make clean` | Remove caches and build artifacts |

## Running with Real AWS

Set `MOCK_MODE=false` in `.env` and configure the S3/OAuth/SSM settings. See `SPEC.md` for full architecture details.

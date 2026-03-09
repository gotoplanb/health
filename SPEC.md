# Sumo Dashboard Viewer — Project Specification

## Overview

A lightweight internal tool that ingests Sumo Logic scheduled report emails, converts the PDF attachments to PNG images, and serves them via a mobile-friendly web application. The goal is to give SRE team members and company stakeholders a fast, authenticated way to view current and recent Sumo Logic dashboard snapshots on any device — without needing access to the Sumo Logic UI.

A secondary goal is to expose structured JSON endpoints so that other internal systems (e.g. deployment pipelines) can query current dashboard state for canary deployment health checks.

---

## Configuration Placeholders

The following placeholders appear throughout this spec and must be substituted with real values before or during implementation:

| Placeholder | Description | Example |
|---|---|---|
| `{SES_SUBDOMAIN}` | Subdomain used for SES inbound email. Should be a subdomain of the company domain to avoid conflicting with Google Workspace MX records. | `sre.example.com` |
| `{INGEST_EMAIL_ADDRESS}` | Full email address Sumo Logic scheduled reports are sent to. | `sumo-dashboards@sre.example.com` |
| `{GOOGLE_WORKSPACE_DOMAIN}` | Google Workspace domain used for OAuth HD check. Only users with email addresses on this domain are granted access. | `example.com` |
| `{AWS_SANDBOX_ACCOUNT_ID}` | AWS account ID for sandbox/proof-of-concept deployment. | `123456789012` |
| `{AWS_PROD_ACCOUNT_ID}` | AWS account ID for production deployment. | `987654321098` |
| `{AWS_REGION}` | Primary AWS region for all resources. | `us-east-1` |

These values should be stored in a `cdk.context.json` file or passed as CDK context variables at deploy time — never hardcoded in application or infrastructure code.

---

## Problem Statement

Sumo Logic's UI is not mobile-friendly. The company has approximately 10 dashboards that SRE cares about. Sumo Logic supports scheduled email delivery of dashboard reports as PDF attachments. This project receives those emails, processes the PDFs into images, stores them, and serves them in a clean viewer with authentication.

---

## Architecture

```
Sumo Logic scheduled delivery (every 15 min)
    → email to sumo-dashboards@{SES_SUBDOMAIN}
    → SES inbound receipt rule
    → raw email dropped to S3 (raw-emails bucket)
    → S3 event notification
    → Lambda: parse email, extract PDF attachment
    → Lambda: convert PDF to PNG, crop whitespace
    → PNG stored to S3 (processed-images bucket)
    → ECS Fargate: FastAPI web app reads from S3
    → CloudFront in front of ECS
    → Google OAuth ({GOOGLE_WORKSPACE_DOMAIN} domain restriction)
    → SSM Parameter Store for programmatic API keys
```

### Key Design Decisions

- **No database.** S3 is the datastore. The processed-images bucket is the source of truth.
- **Lambda for processing.** PDF arrival is event-driven, not polled. Lambda is the right tool.
- **ECS Fargate for the web app.** Long-running, needs session state, and may grow to serve additional API use cases.
- **CloudFront in front of ECS.** Standard pattern; enables caching of static assets, HTTPS termination.
- **Raw PDFs retained longer than rendered PNGs.** PDFs kept 30 days for potential data team use. PNGs pruned to 3 hours since they only serve the UI.
- **Subdomain for SES inbound.** `{SES_SUBDOMAIN}` MX record points to SES. Does not conflict with Google Workspace MX records on the root domain.

---

## AWS Infrastructure (CDK)

All infrastructure is defined in a single CDK app. Proof-of-concept work happens in a sandbox AWS account before promotion to production.

### CDK Stack: `SumoDashboardViewerStack`

#### Route 53
- Add MX record for `{SES_SUBDOMAIN}` pointing to SES inbound SMTP endpoint for the deployment region
- Add SES domain verification TXT record for `{SES_SUBDOMAIN}`
- Add DKIM CNAME records for `{SES_SUBDOMAIN}`

#### SES
- Verify domain `{SES_SUBDOMAIN}`
- Create inbound receipt rule set (or add to existing active rule set)
- Receipt rule: matches `sumo-dashboards@{SES_SUBDOMAIN}`, action is S3 delivery to raw-emails bucket
- Receipt rule should be ordered to run before any catch-all rules

#### S3: Raw Emails Bucket (`sumo-dashboard-raw-emails`)
- Private, no public access
- Lifecycle rule: delete objects after 30 days
- Versioning: disabled
- Event notification: trigger processing Lambda on `s3:ObjectCreated:*`

#### S3: Processed Images Bucket (`sumo-dashboard-images`)
- Private, no public access
- Lifecycle rule: delete PNG objects after 3 hours
- Lifecycle rule: delete PDF objects after 30 days (PDFs also copied here for data team access)
- Object key structure: `dashboards/{dashboard-name}/{iso-timestamp}.png`
- Also store raw PDFs at: `pdfs/{dashboard-name}/{iso-timestamp}.pdf`

#### Lambda: Email Processor (`sumo-email-processor`)
- Triggered by S3 event from raw-emails bucket
- Runtime: Python 3.12
- Responsibilities:
  - Parse raw email (MIME)
  - Extract PDF attachment
  - Derive dashboard name from email subject line (subject is the dashboard name, e.g. `My Dashboard Name`)
  - Sanitize dashboard name for use as S3 key (lowercase, hyphens)
  - Store PDF to processed-images bucket under `pdfs/` prefix
  - Trigger (or directly invoke) the image conversion Lambda
- IAM: read from raw-emails bucket, write to processed-images bucket, invoke conversion Lambda

#### Lambda: PDF Converter (`sumo-pdf-converter`)
- Invoked by email processor Lambda (synchronous invoke)
- Runtime: Python 3.12 with Lambda layer containing `pdf2image` and `poppler`
- Responsibilities:
  - Receive S3 key of PDF as input
  - Download PDF from S3
  - Convert to PNG using `pdf2image` at high resolution (300 DPI)
  - Crop bottom whitespace (detect and trim rows of near-black pixels below content)
  - Store PNG to processed-images bucket under `dashboards/` prefix
  - Key format: `dashboards/{dashboard-name}/{iso-timestamp}.png`
- IAM: read/write processed-images bucket

**Note on poppler Lambda layer:** `pdf2image` requires `poppler` binaries. Use a pre-built Lambda layer for poppler (e.g. from `jeylabs/poppler-lambda-layer` or build one as part of CDK using a Docker-based asset). Document the layer ARN or build process clearly.

#### SSM Parameter Store
- Prefix: `/sumo-viewer/api-keys/{client-name}`
- Type: `SecureString`
- The FastAPI app reads all parameters under this prefix at startup
- Adding a new client = adding a new SSM parameter (no redeployment required, app picks up on restart)
- CDK provisions the parameter path and IAM access; actual key values are set manually or via CI

#### ECS Fargate: FastAPI App (`sumo-viewer-service`)
- Single service, single container
- Task role IAM permissions:
  - Read from processed-images bucket (list + get)
  - Read SSM parameters under `/sumo-viewer/api-keys/` prefix
- Environment variables (injected at task startup):
  - `S3_IMAGES_BUCKET`
  - `GOOGLE_CLIENT_ID`
  - `GOOGLE_CLIENT_SECRET` (from Secrets Manager — this one is sensitive)
  - `SESSION_SECRET_KEY` (from Secrets Manager)
  - `ALLOWED_DOMAIN={GOOGLE_WORKSPACE_DOMAIN}`
  - `SSM_API_KEYS_PREFIX=/sumo-viewer/api-keys/`
- Health check endpoint: `GET /health` (no auth required)

#### CloudFront
- Origin: ECS service via Application Load Balancer
- HTTPS only
- Cache behavior: cache static assets (`/static/*`), pass-through all other requests
- No caching on API or dashboard routes (content changes every 15 min)

---

## Application: FastAPI Web App

### Tech Stack
- **Framework:** FastAPI
- **Templating:** Jinja2 (for HTMX-driven HTML responses)
- **Frontend:** HTMX + Alpine.js + Tailwind CSS
- **Auth (browser):** Google OAuth via `authlib`
- **Auth (programmatic):** API key in `X-API-Key` header
- **S3 access:** `boto3`
- **Session middleware:** Starlette `SessionMiddleware`

### Project Structure

```
app/
  main.py               # FastAPI app, middleware, router registration
  config.py             # Settings via pydantic-settings, reads env vars
  auth/
    google.py           # Google OAuth flow, HD domain check
    api_key.py          # SSM parameter fetch, API key dependency
    dependencies.py     # FastAPI dependency functions for both auth paths
  s3/
    client.py           # Boto3 S3 wrapper
    models.py           # Snapshot dataclass: dashboard_name, timestamp, s3_key, url
  routers/
    web.py              # Browser routes (Google OAuth protected, HTML responses)
    api.py              # Programmatic routes (API key protected, JSON responses)
    auth.py             # OAuth callback, login, logout routes
  templates/
    base.html
    index.html          # Dashboard grid, latest snapshots
    dashboard.html      # Single dashboard view with history strip
  static/
    (Tailwind output, Alpine.js)
tests/
  test_s3.py
  test_auth.py
  test_routers.py
lambda/
  email_processor/
    handler.py
    requirements.txt
    tests/
  pdf_converter/
    handler.py
    requirements.txt
    tests/
cdk/
  app.py
  stacks/
    sumo_dashboard_viewer_stack.py
  tests/
```

### Authentication: Browser Routes

- All routes under `/` except `/health`, `/auth/login`, `/auth/callback` require a valid Google OAuth session
- OAuth flow:
  - `GET /auth/login` → redirect to Google
  - `GET /auth/callback` → validate token, check `hd` claim equals `{GOOGLE_WORKSPACE_DOMAIN}`, set session cookie
  - `GET /auth/logout` → clear session
- If HD check fails, return 403
- Use `authlib` with Starlette session middleware
- Session cookie is HTTP-only, secure

### Authentication: API Routes

- All routes under `/api/v1/` require `X-API-Key` header
- On startup, FastAPI app fetches all SSM parameters under `/sumo-viewer/api-keys/` prefix
- Builds an in-memory set of valid key values
- FastAPI dependency `require_api_key` checks incoming header against this set
- 401 if missing or invalid
- Keys are refreshed from SSM on every ECS task restart (no live refresh needed for now)

### Web Routes (HTML, HTMX)

#### `GET /`
- Requires Google session
- Lists all dashboards (derived from S3 key prefixes under `dashboards/`)
- Shows latest snapshot image for each dashboard
- Shows timestamp of latest snapshot and a staleness indicator (warn if > 30 min old)
- Mobile-first grid layout

#### `GET /dashboards/{name}`
- Requires Google session
- Shows current (latest) PNG for the named dashboard, full width
- Below: horizontal scrollable strip of historical snapshots from last 3 hours
- Clicking a historical snapshot replaces the main image (HTMX swap)
- Shows timestamp for each snapshot

#### `GET /dashboards/{name}/snapshot/{timestamp}`
- HTMX partial — returns just the image element for the requested snapshot
- Used by history strip clicks

### API Routes (JSON)

#### `GET /api/v1/dashboards`
- Requires API key
- Returns list of all dashboard names and their latest snapshot timestamp
```json
{
  "dashboards": [
    {
      "name": "my-dashboard-name",
      "display_name": "My Dashboard Name",
      "latest_snapshot": "2026-01-01T07:00:00Z",
      "age_seconds": 342,
      "stale": false
    }
  ]
}
```

#### `GET /api/v1/dashboards/{name}/status`
- Requires API key
- Returns status for a single dashboard for canary/health check use
- `stale: true` if latest snapshot is > 30 minutes old
```json
{
  "name": "my-dashboard-name",
  "display_name": "My Dashboard Name",
  "latest_snapshot": "2026-01-01T07:00:00Z",
  "age_seconds": 342,
  "stale": false,
  "snapshot_url": "https://..."
}
```

#### `GET /health`
- No auth required
- Returns 200 with `{"status": "ok"}`
- Used by ECS health check and ALB target group health check

### Staleness Logic
- A snapshot is considered stale if `now - latest_snapshot_timestamp > 30 minutes`
- This is displayed visually in the UI (amber warning indicator) and as a field in API responses
- The threshold should be configurable via environment variable `STALE_THRESHOLD_MINUTES` (default: 30)

---

## Lambda: Email Processor Detail

```python
# Triggered by S3 ObjectCreated event
# Event contains bucket name and object key of raw email

def handler(event, context):
    # 1. Get S3 object key from event
    # 2. Download raw email from S3
    # 3. Parse with Python email.parser
    # 4. Extract subject line → dashboard display name
    # 5. Sanitize to slug: lowercase, spaces→hyphens, strip special chars
    # 6. Find PDF attachment in MIME parts (content-type: application/pdf)
    # 7. Generate ISO timestamp (use email Date header, fall back to now())
    # 8. Upload PDF to processed-images bucket: pdfs/{slug}/{timestamp}.pdf
    # 9. Invoke pdf-converter Lambda with payload:
    #    {"bucket": "...", "pdf_key": "...", "dashboard_name": slug, "timestamp": "..."}
```

### Email Subject Parsing
- Sumo Logic sends the dashboard name as the email subject verbatim (e.g. `My Dashboard Name`)
- Slug conversion: `"My Dashboard Name"` → `"my-dashboard-name"`
- Store display name alongside slug for UI rendering (can derive from slug or store in S3 object metadata)

---

## Lambda: PDF Converter Detail

```python
def handler(event, context):
    # 1. Download PDF from S3 using event payload
    # 2. Write to /tmp (Lambda ephemeral storage)
    # 3. pdf2image.convert_from_path(pdf_path, dpi=300)
    # 4. Should produce single-page PNG for most Sumo dashboards
    # 5. Crop: scan from bottom, find last row where any pixel is not near-black
    #    (threshold: any channel > 20), trim everything below
    # 6. Save PNG to /tmp
    # 7. Upload to S3: dashboards/{dashboard_name}/{timestamp}.png
    # 8. Set S3 object metadata: dashboard_name, timestamp, source_pdf_key
```

---

## S3 Key Conventions

```
raw-emails bucket:
  {ses-message-id}                          (raw email, SES default naming)

processed-images bucket:
  pdfs/{dashboard-name}/{iso-timestamp}.pdf
  dashboards/{dashboard-name}/{iso-timestamp}.png
```

Timestamp format: `YYYY-MM-DDTHH-MM-SSZ` (colons replaced with hyphens for S3 key safety)

---

## Testing

### Lambda Tests
- Email processor: test with fixture raw emails (real email saved as .eml file)
  - Test subject parsing and slug generation
  - Test PDF extraction from MIME
  - Test S3 upload calls (mocked with `moto`)
  - Test Lambda invocation call (mocked)
- PDF converter: test with a sample Sumo Logic PDF export (committed to `lambda/pdf_converter/tests/fixtures/sample_dashboard.pdf`)
  - Test conversion produces a PNG
  - Test whitespace cropping removes bottom blank area
  - Test S3 upload (mocked with `moto`)

### FastAPI Tests
- Auth dependency tests: valid session, missing session, valid API key, invalid API key
- Route tests using `TestClient`
- S3 client tests with `moto`

### CDK Tests
- Snapshot tests for key resources (SES rule, S3 buckets, Lambda functions, ECS service)

---

## Development & Deployment

### Local Development
- Run FastAPI app locally with `uvicorn`
- Use `ngrok` for Google OAuth callback URL during local dev
- Point Google OAuth redirect URI to ngrok URL
- Use AWS profile with sandbox account credentials
- Mock S3 locally with `moto` in tests, or point at sandbox S3 bucket directly

### Sandbox Account Workflow
1. Deploy CDK stack to sandbox account
2. Verify SES domain `{SES_SUBDOMAIN}` (requires Route 53 changes)
3. Send test email to `sumo-dashboards@{SES_SUBDOMAIN}`
4. Verify Lambda chain fires and PNG appears in S3
5. Verify FastAPI app serves images correctly
6. Verify Google OAuth flow works end to end
7. Verify API key auth works

### Production Promotion
- Update CDK environment to production account
- Re-verify SES domain in production account (or share verification if using same domain)
- Update Google OAuth app with production CloudFront URL as allowed redirect URI
- Rotate all SSM API keys (don't reuse sandbox values)

---

## Local Mock Mode

To enable fast UI development and stakeholder demos without any AWS infrastructure, the FastAPI app supports a local mock mode that serves images from the filesystem instead of S3.

### Enabling Mock Mode

Set the following in a `.env` file at the project root:

```
MOCK_MODE=true
MOCK_DATA_DIR=mock-data
```

When `MOCK_MODE=true`, the app's S3 client is swapped for a local filesystem client that reads from `MOCK_DATA_DIR`. All application logic, routing, auth, and templating remain identical — only the data source changes.

### Mock Data Directory Structure

The `mock-data/` directory mirrors the S3 processed-images bucket key structure exactly:

```
mock-data/
  dashboards/
    my-first-dashboard/
      2026-01-01T07-00-00Z.png
      2026-01-01T06-45-00Z.png
      2026-01-01T06-30-00Z.png
    my-second-dashboard/
      2026-01-01T07-00-00Z.png
      2026-01-01T06-45-00Z.png
    my-third-dashboard/
      2026-01-01T07-00-00Z.png
```

- Directory names under `dashboards/` are the dashboard slugs
- Filenames are timestamps in `YYYY-MM-DDTHH-MM-SSZ` format (same as production)
- PNGs are real dashboard screenshots converted manually from Sumo PDF exports
- `mock-data/` is gitignored — it is never committed to the repo

### Filesystem Client

The app has a storage abstraction with two implementations:

```python
# app/s3/client.py
class StorageClient(Protocol):
    def list_dashboards(self) -> list[str]: ...
    def list_snapshots(self, dashboard_name: str, since: datetime) -> list[Snapshot]: ...
    def get_snapshot_url(self, key: str) -> str: ...

class S3StorageClient:
    # Production: reads from S3, generates presigned URLs
    ...

class LocalStorageClient:
    # Mock mode: reads from MOCK_DATA_DIR, returns file:// or /static/ URLs
    # Serves images via a FastAPI static files mount on /mock-static/
    ...
```

The correct implementation is injected at startup based on `MOCK_MODE` setting. No other application code is aware of which backend is in use.

### Running in Mock Mode

```bash
# 1. Convert a Sumo PDF export to PNG manually (one-time per dashboard)
#    Use pdf2image or any PDF viewer's export function
#    Crop bottom whitespace if desired

# 2. Place PNGs in the correct directory structure under mock-data/

# 3. Set env vars
cp .env.example .env
# Set MOCK_MODE=true in .env

# 4. Start the app
uvicorn app.main:app --reload

# 5. Optionally expose via ngrok for stakeholder demos
ngrok http 8000
```

### Google OAuth in Mock Mode

Google OAuth still applies in mock mode by default (you are still testing the real auth flow). To skip auth entirely during local UI development, add:

```
MOCK_AUTH=true
```

When `MOCK_AUTH=true`, all routes behave as if a user is authenticated with a fake session. This should never be enabled in any deployed environment. The `require_google_session` dependency checks this flag and short-circuits if set.

### What Mock Mode Tests

- Full UI layout and mobile feel
- HTMX interactions (history strip, image swapping)
- Dashboard index page with staleness indicators
- Stakeholder demos via ngrok without any AWS setup
- Frontend changes with fast iteration cycle

### What Mock Mode Does Not Test

- SES inbound email receipt
- Lambda PDF processing chain
- S3 presigned URL generation
- Real Google OAuth token validation (if `MOCK_AUTH=true`)

### Populating Mock Data

To generate initial mock PNGs from Sumo:
1. Go to each dashboard in Sumo Logic
2. Use the existing scheduled report delivery to get a PDF, or export manually
3. Convert PDF to PNG: `pdftoppm -r 300 -png dashboard.pdf output` (requires poppler)
4. Crop and rename to timestamp format
5. Place in correct `mock-data/dashboards/{slug}/` directory

The `pdf_converter` Lambda handler can be run locally as a script to automate this if poppler is installed locally.

---

## Open Items / Future Considerations

- **PDF multi-page handling:** Current Sumo dashboards appear to be single-page. If a dashboard produces multi-page PDF, converter should either stitch pages vertically or store as multiple images. Flag this if encountered.
- **Live SSM key refresh:** Currently API keys are loaded at startup. If zero-restart key provisioning becomes needed, add a background refresh task (e.g. every 5 minutes).
- **Data team pipeline:** Raw PDFs in S3 under `pdfs/` prefix with 30-day retention are available for downstream processing. No action needed now.
- **Alerting:** Consider a CloudWatch alarm if the Lambda error rate spikes or if no new images have arrived in > 20 minutes during business hours.
- **Multiple environments:** If a dashboard has multiple environments (e.g. `prod` vs `staging` filter), Sumo will send separate scheduled reports. These will arrive as separate emails with the same dashboard name. Consider whether the subject line will differentiate them or if a naming convention in Sumo is needed.

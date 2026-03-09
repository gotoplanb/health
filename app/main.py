from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.routers import api, auth, web
from app.s3.client import LocalStorageClient, S3StorageClient, StorageClient

app = FastAPI(title="Sumo Dashboard Viewer")

# Session middleware for Google OAuth
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret_key)

# Storage backend
storage: StorageClient
if settings.mock_mode:
    storage = LocalStorageClient(base_dir=Path(settings.mock_data_dir))
    # Serve mock images as static files
    mock_path = Path(settings.mock_data_dir)
    if mock_path.exists():
        app.mount("/mock-static", StaticFiles(directory=str(mock_path)), name="mock-static")
else:
    storage = S3StorageClient(bucket=settings.s3_images_bucket)

app.state.storage = storage

# Static files
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Routers
app.include_router(auth.router)
app.include_router(web.router)
app.include_router(api.router)


@app.get("/health")
async def health():
    return {"status": "ok"}

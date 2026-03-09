from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.auth.dependencies import require_google_session
from app.config import settings
from app.s3.client import StorageClient

router = APIRouter(tags=["web"])
templates = Jinja2Templates(directory="app/templates")


def _get_storage(request: Request) -> StorageClient:
    return request.app.state.storage


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, user: dict = Depends(require_google_session)):
    storage = _get_storage(request)
    dashboards = storage.list_dashboards()
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=3)
    stale_threshold = timedelta(minutes=settings.stale_threshold_minutes)

    dashboard_data = []
    for name in dashboards:
        snapshots = storage.list_snapshots(name, since)
        latest = snapshots[0] if snapshots else None
        is_stale = latest is None or (now - latest.timestamp) > stale_threshold
        dashboard_data.append({
            "name": name,
            "display_name": name.replace("-", " ").title(),
            "latest": latest,
            "stale": is_stale,
        })

    return templates.TemplateResponse("index.html", {
        "request": request,
        "dashboards": dashboard_data,
        "user": user,
    })


@router.get("/dashboards/{name}", response_class=HTMLResponse)
async def dashboard_detail(request: Request, name: str, user: dict = Depends(require_google_session)):
    storage = _get_storage(request)
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=3)
    snapshots = storage.list_snapshots(name, since)
    latest = snapshots[0] if snapshots else None

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "name": name,
        "display_name": name.replace("-", " ").title(),
        "latest": latest,
        "snapshots": snapshots,
        "user": user,
    })


@router.get("/dashboards/{name}/snapshot/{timestamp}", response_class=HTMLResponse)
async def snapshot_partial(request: Request, name: str, timestamp: str, user: dict = Depends(require_google_session)):
    """HTMX partial: returns just the image element for a specific snapshot."""
    storage = _get_storage(request)
    key = f"dashboards/{name}/{timestamp}.png"
    url = storage.get_snapshot_url(key)
    return HTMLResponse(f'<img src="{url}" alt="{name}" class="w-full rounded-lg shadow">')

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.auth.dependencies import require_google_session
from app.config import settings
from app.s3.client import StorageClient, parse_timestamp

router = APIRouter(tags=["web"])
templates = Jinja2Templates(directory="app/templates")


def _get_storage(request: Request) -> StorageClient:
    return request.app.state.storage


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, user: dict = Depends(require_google_session)):
    storage = _get_storage(request)
    dashboards = storage.list_dashboards()
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=365)
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
    since = now - timedelta(days=365)
    stale_threshold = timedelta(minutes=settings.stale_threshold_minutes)
    snapshots = storage.list_snapshots(name, since)

    snapshot_data = []
    for snap in snapshots:
        age = now - snap.timestamp
        is_stale = age > stale_threshold
        snapshot_data.append({
            "snapshot": snap,
            "stale": is_stale,
            "timestamp_slug": snap.timestamp.strftime("%Y-%m-%dT%H-%M-%SZ"),
        })

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "name": name,
        "display_name": name.replace("-", " ").title(),
        "snapshots": snapshot_data,
        "user": user,
    })


@router.get("/dashboards/{name}/snapshot/{timestamp}", response_class=HTMLResponse)
async def snapshot_detail(request: Request, name: str, timestamp: str, user: dict = Depends(require_google_session)):
    storage = _get_storage(request)
    key = f"dashboards/{name}/{timestamp}.png"
    url = storage.get_snapshot_url(key)
    try:
        ts = parse_timestamp(f"{timestamp}.png")
    except ValueError:
        raise HTTPException(status_code=404, detail="Invalid timestamp")

    return templates.TemplateResponse("snapshot.html", {
        "request": request,
        "name": name,
        "display_name": name.replace("-", " ").title(),
        "timestamp": ts,
        "url": url,
        "user": user,
    })

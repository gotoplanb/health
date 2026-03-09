from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import require_api_key
from app.config import settings
from app.s3.client import StorageClient

router = APIRouter(prefix="/api/v1", tags=["api"])


def _get_storage(request: Request) -> StorageClient:
    return request.app.state.storage


@router.get("/dashboards")
async def list_dashboards(request: Request, _key: str = Depends(require_api_key)):
    storage = _get_storage(request)
    dashboards = storage.list_dashboards()
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=3)
    stale_threshold = timedelta(minutes=settings.stale_threshold_minutes)

    result = []
    for name in dashboards:
        snapshots = storage.list_snapshots(name, since)
        latest = snapshots[0] if snapshots else None
        age = int((now - latest.timestamp).total_seconds()) if latest else None
        result.append({
            "name": name,
            "display_name": name.replace("-", " ").title(),
            "latest_snapshot": latest.timestamp.isoformat() if latest else None,
            "age_seconds": age,
            "stale": latest is None or (now - latest.timestamp) > stale_threshold,
        })

    return {"dashboards": result}


@router.get("/dashboards/{name}/status")
async def dashboard_status(request: Request, name: str, _key: str = Depends(require_api_key)):
    storage = _get_storage(request)
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=3)
    stale_threshold = timedelta(minutes=settings.stale_threshold_minutes)

    snapshots = storage.list_snapshots(name, since)
    if not snapshots:
        raise HTTPException(status_code=404, detail=f"No snapshots found for dashboard '{name}'")

    latest = snapshots[0]
    age = int((now - latest.timestamp).total_seconds())

    return {
        "name": name,
        "display_name": name.replace("-", " ").title(),
        "latest_snapshot": latest.timestamp.isoformat(),
        "age_seconds": age,
        "stale": (now - latest.timestamp) > stale_threshold,
        "snapshot_url": latest.url,
    }

from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

import boto3

from app.s3.models import Snapshot

# Timestamp format used in S3 keys (colons replaced with hyphens)
TIMESTAMP_FORMAT = "%Y-%m-%dT%H-%M-%SZ"


def parse_timestamp(name: str) -> datetime:
    """Parse a timestamp from a filename like '2026-01-01T07-00-00Z.png'."""
    stem = name.rsplit(".", 1)[0]
    return datetime.strptime(stem, TIMESTAMP_FORMAT).replace(tzinfo=timezone.utc)


class StorageClient(Protocol):
    def list_dashboards(self) -> list[str]: ...
    def list_snapshots(self, dashboard_name: str, since: datetime) -> list[Snapshot]: ...
    def get_snapshot_url(self, key: str) -> str: ...


class S3StorageClient:
    """Production: reads from S3, generates presigned URLs."""

    def __init__(self, bucket: str) -> None:
        self.bucket = bucket
        self.s3 = boto3.client("s3")

    def list_dashboards(self) -> list[str]:
        paginator = self.s3.get_paginator("list_objects_v2")
        dashboards: set[str] = set()
        for page in paginator.paginate(Bucket=self.bucket, Prefix="dashboards/", Delimiter="/"):
            for prefix in page.get("CommonPrefixes", []):
                # prefix looks like "dashboards/my-dashboard-name/"
                name = prefix["Prefix"].split("/")[1]
                dashboards.add(name)
        return sorted(dashboards)

    def list_snapshots(self, dashboard_name: str, since: datetime) -> list[Snapshot]:
        prefix = f"dashboards/{dashboard_name}/"
        paginator = self.s3.get_paginator("list_objects_v2")
        snapshots: list[Snapshot] = []
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                filename = key.rsplit("/", 1)[-1]
                try:
                    ts = parse_timestamp(filename)
                except ValueError:
                    continue
                if ts >= since:
                    snapshots.append(Snapshot(
                        dashboard_name=dashboard_name,
                        timestamp=ts,
                        s3_key=key,
                        url=self.get_snapshot_url(key),
                    ))
        snapshots.sort(key=lambda s: s.timestamp, reverse=True)
        return snapshots

    def get_snapshot_url(self, key: str) -> str:
        return self.s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=3600,
        )


class LocalStorageClient:
    """Mock mode: reads from local filesystem, returns static file URLs."""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.dashboards_dir = base_dir / "dashboards"

    def list_dashboards(self) -> list[str]:
        if not self.dashboards_dir.exists():
            return []
        return sorted(d.name for d in self.dashboards_dir.iterdir() if d.is_dir())

    def list_snapshots(self, dashboard_name: str, since: datetime) -> list[Snapshot]:
        dashboard_dir = self.dashboards_dir / dashboard_name
        if not dashboard_dir.exists():
            return []
        snapshots: list[Snapshot] = []
        for f in dashboard_dir.iterdir():
            if f.suffix != ".png":
                continue
            try:
                ts = parse_timestamp(f.name)
            except ValueError:
                continue
            if ts >= since:
                key = f"dashboards/{dashboard_name}/{f.name}"
                snapshots.append(Snapshot(
                    dashboard_name=dashboard_name,
                    timestamp=ts,
                    s3_key=key,
                    url=f"/mock-static/{key}",
                ))
        snapshots.sort(key=lambda s: s.timestamp, reverse=True)
        return snapshots

    def get_snapshot_url(self, key: str) -> str:
        return f"/mock-static/{key}"

"""Tests for S3 storage client."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from app.s3.client import LocalStorageClient, parse_timestamp


class TestParseTimestamp:
    def test_parses_valid_timestamp(self):
        ts = parse_timestamp("2026-01-01T07-00-00Z.png")
        assert ts == datetime(2026, 1, 1, 7, 0, 0, tzinfo=timezone.utc)

    def test_parses_without_extension(self):
        ts = parse_timestamp("2026-03-09T14-30-00Z")
        assert ts == datetime(2026, 3, 9, 14, 30, 0, tzinfo=timezone.utc)


class TestLocalStorageClient:
    def test_list_dashboards_empty(self):
        with TemporaryDirectory() as tmpdir:
            client = LocalStorageClient(base_dir=Path(tmpdir))
            assert client.list_dashboards() == []

    def test_list_dashboards(self):
        with TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            (base / "dashboards" / "alpha-dashboard").mkdir(parents=True)
            (base / "dashboards" / "beta-dashboard").mkdir(parents=True)
            client = LocalStorageClient(base_dir=base)
            assert client.list_dashboards() == ["alpha-dashboard", "beta-dashboard"]

    def test_list_snapshots(self):
        with TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            dash_dir = base / "dashboards" / "test-dash"
            dash_dir.mkdir(parents=True)
            (dash_dir / "2026-01-01T07-00-00Z.png").write_bytes(b"fake png")
            (dash_dir / "2026-01-01T06-00-00Z.png").write_bytes(b"fake png")

            client = LocalStorageClient(base_dir=base)
            since = datetime(2026, 1, 1, 5, 0, 0, tzinfo=timezone.utc)
            snapshots = client.list_snapshots("test-dash", since)
            assert len(snapshots) == 2
            # Sorted newest first
            assert snapshots[0].timestamp > snapshots[1].timestamp

    def test_list_snapshots_filters_by_since(self):
        with TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            dash_dir = base / "dashboards" / "test-dash"
            dash_dir.mkdir(parents=True)
            (dash_dir / "2026-01-01T07-00-00Z.png").write_bytes(b"fake png")
            (dash_dir / "2026-01-01T03-00-00Z.png").write_bytes(b"fake png")

            client = LocalStorageClient(base_dir=base)
            since = datetime(2026, 1, 1, 5, 0, 0, tzinfo=timezone.utc)
            snapshots = client.list_snapshots("test-dash", since)
            assert len(snapshots) == 1

    def test_get_snapshot_url(self):
        with TemporaryDirectory() as tmpdir:
            client = LocalStorageClient(base_dir=Path(tmpdir))
            url = client.get_snapshot_url("dashboards/test/2026-01-01T07-00-00Z.png")
            assert url == "/mock-static/dashboards/test/2026-01-01T07-00-00Z.png"

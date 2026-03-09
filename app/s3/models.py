from dataclasses import dataclass
from datetime import datetime


@dataclass
class Snapshot:
    dashboard_name: str
    timestamp: datetime
    s3_key: str
    url: str

    @property
    def display_name(self) -> str:
        """Convert slug back to display name: 'my-dashboard-name' -> 'My Dashboard Name'."""
        return self.dashboard_name.replace("-", " ").title()

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
import json

MISSION_STATES = {"planned", "active", "paused", "completed", "aborted"}
OBS_STATES = {"pending", "accepted", "rejected", "quarantined"}

def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()

@dataclass
class Mission:
    id: str
    vessel_id: str
    name: str
    status: str
    max_duration_min: int
    transects: list[dict[str, Any]]
    created_by: str
    version: int = 1

@dataclass
class Observation:
    id: str
    mission_id: str
    sequence_no: int
    observed_at: str
    latitude: float
    longitude: float
    depth_m: float
    measurements: dict[str, float]
    quality_status: str = "pending"
    quality_flags: list[str] | None = None
    ingestion_id: str = ""

    def as_dict(self):
        return {"id": self.id, "mission_id": self.mission_id, "sequence_no": self.sequence_no,
                "observed_at": self.observed_at, "latitude": self.latitude, "longitude": self.longitude,
                "depth_m": self.depth_m, "measurements": self.measurements,
                "quality_status": self.quality_status, "quality_flags": self.quality_flags or [],
                "ingestion_id": self.ingestion_id}

def json_load(value: str, default):
    try: return json.loads(value)
    except (TypeError, json.JSONDecodeError): return default

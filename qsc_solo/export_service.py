import hashlib, json, uuid
from .audit import record
from .auth import require
from .errors import Conflict, NotFound
from .models import utcnow

class ExportService:
    def __init__(self, db): self.db = db

    def create(self, mission_id, actor, role, include_quarantined=False):
        require(role, "export:write")
        with self.db.transaction() as c:
            mission = c.execute("SELECT status FROM missions WHERE id=?", (mission_id,)).fetchone()
            if not mission: raise NotFound("mission not found")
            if mission["status"] != "completed": raise Conflict("exports require a completed mission")
            if include_quarantined and role != "scientist": raise Conflict("only a scientist may include quarantined observations")
            statuses = ("accepted", "quarantined") if include_quarantined else ("accepted",)
            placeholders = ",".join("?" for _ in statuses)
            rows = c.execute(f"SELECT sequence_no,observed_at,latitude,longitude,depth_m,measurements_json,quality_status,quality_flags_json FROM observations WHERE mission_id=? AND quality_status IN ({placeholders}) ORDER BY sequence_no", (mission_id, *statuses)).fetchall()
            payload = [dict(r) for r in rows]
            digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(); eid = str(uuid.uuid4())
            c.execute("INSERT INTO exports VALUES(?,?,?,?,?,?,?)", (eid, mission_id, actor, int(include_quarantined), len(payload), digest, utcnow()))
            record(c, actor, "mission.exported", "mission", mission_id, {"export_id": eid, "count": len(payload), "hash": digest})
            return {"export_id": eid, "mission_id": mission_id, "observation_count": len(payload), "content_hash": digest, "observations": payload}

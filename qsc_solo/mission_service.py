import json, uuid
from .audit import record
from .errors import Conflict, NotFound, ValidationError
from .models import Mission, MISSION_STATES, utcnow, json_load

class MissionService:
    def __init__(self, db): self.db = db

    def create(self, vessel_id, name, transects, max_duration_min, actor):
        if not vessel_id or not name: raise ValidationError("vessel_id and name are required")
        if not isinstance(transects, list) or len(transects) < 1: raise ValidationError("at least one transect is required")
        if max_duration_min <= 0: raise ValidationError("max_duration_min must be positive")
        for i, t in enumerate(transects):
            if not isinstance(t, dict) or not all(k in t for k in ("latitude", "longitude", "depth_m")):
                raise ValidationError(f"transect {i} is missing coordinates")
            if not (-90 <= t["latitude"] <= 90 and -180 <= t["longitude"] <= 180 and t["depth_m"] >= 0):
                raise ValidationError(f"transect {i} has invalid coordinates")
        mid = str(uuid.uuid4())
        with self.db.transaction() as c:
            now = utcnow(); c.execute("INSERT INTO missions VALUES(?,?,?,?,?,?,?,?,?,?)",
                (mid, vessel_id, name, "planned", max_duration_min, json.dumps(transects), actor, 1, now, now))
            record(c, actor, "mission.created", "mission", mid, {"transects": len(transects)})
        return self.get(mid)

    def get(self, mission_id):
        with self.db.connect() as c:
            row = c.execute("SELECT * FROM missions WHERE id=?", (mission_id,)).fetchone()
        if not row: raise NotFound("mission not found")
        return Mission(row["id"], row["vessel_id"], row["name"], row["status"], row["max_duration_min"], json_load(row["transects_json"], []), row["created_by"], row["version"])

    def transition(self, mission_id, target, actor):
        allowed = {"planned": {"active", "aborted"}, "active": {"paused", "completed", "aborted"}, "paused": {"active", "aborted"}, "completed": set(), "aborted": set()}
        with self.db.transaction() as c:
            row = c.execute("SELECT * FROM missions WHERE id=?", (mission_id,)).fetchone()
            if not row: raise NotFound("mission not found")
            current = row["status"]
            if target not in allowed[current]: raise Conflict(f"cannot transition {current} -> {target}")
            if target == "active":
                lock = c.execute("SELECT mission_id FROM vessel_locks WHERE vessel_id=?", (row["vessel_id"],)).fetchone()
                if lock and lock["mission_id"] != mission_id: raise Conflict("vessel already assigned to another active mission")
                c.execute("INSERT OR REPLACE INTO vessel_locks(vessel_id,mission_id,acquired_at) VALUES(?,?,?)", (row["vessel_id"], mission_id, utcnow()))
            if current == "active" and target in {"paused", "completed", "aborted"}: c.execute("DELETE FROM vessel_locks WHERE vessel_id=?", (row["vessel_id"],))
            c.execute("UPDATE missions SET status=?,version=version+1,updated_at=? WHERE id=?", (target, utcnow(), mission_id))
            record(c, actor, f"mission.{target}", "mission", mission_id, {"from": current, "to": target})
        return self.get(mission_id)

    def status(self, mission_id):
        mission = self.get(mission_id)
        with self.db.connect() as c:
            counts = {r["quality_status"]: r["n"] for r in c.execute("SELECT quality_status,COUNT(*) n FROM observations WHERE mission_id=? GROUP BY quality_status", (mission_id,))}
            checkpoint = c.execute("SELECT last_sequence FROM checkpoints WHERE mission_id=?", (mission_id,)).fetchone()
            incidents = c.execute("SELECT COUNT(*) n FROM incidents WHERE mission_id=? AND state!='resolved'", (mission_id,)).fetchone()["n"]
        return {"mission": mission.__dict__, "observation_counts": counts, "checkpoint": checkpoint["last_sequence"] if checkpoint else 0, "open_incidents": incidents}

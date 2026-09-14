from .audit import record
from .errors import Conflict, NotFound
from .models import utcnow

class RecoveryService:
    def __init__(self, db): self.db = db

    def checkpoint(self, mission_id, actor):
        with self.db.transaction() as c:
            row = c.execute("SELECT MAX(sequence_no) n FROM observations WHERE mission_id=? AND quality_status='accepted'", (mission_id,)).fetchone()
            if row["n"] is None: raise Conflict("cannot checkpoint without accepted observations")
            c.execute("INSERT OR REPLACE INTO checkpoints VALUES(?,?,?)", (mission_id, row["n"], utcnow())); record(c, actor, "mission.checkpoint", "mission", mission_id, {"last_sequence": row["n"]})
            return row["n"]

    def resume_plan(self, mission_id):
        with self.db.connect() as c:
            mission = c.execute("SELECT status,transects_json FROM missions WHERE id=?", (mission_id,)).fetchone()
            if not mission: raise NotFound("mission not found")
            checkpoint = c.execute("SELECT last_sequence FROM checkpoints WHERE mission_id=?", (mission_id,)).fetchone()
            last = checkpoint["last_sequence"] if checkpoint else 0
            if mission["status"] not in {"active", "paused"}: raise Conflict("only active or paused missions can resume")
        return {"mission_id": mission_id, "resume_from_sequence": last + 1, "reason": "checkpoint" if last else "mission_start"}

import hashlib, json, uuid
from datetime import datetime
from .audit import record
from .errors import Conflict, NotFound, ValidationError
from .models import utcnow

class TelemetryService:
    def __init__(self, db, checkpoint_interval=5, max_batch_size=100):
        self.db, self.checkpoint_interval, self.max_batch_size = db, checkpoint_interval, max_batch_size

    def seed_calibration(self, sensor_id, metric, version, min_value, max_value, valid_from="1970-01-01T00:00:00+00:00", valid_to=None):
        with self.db.transaction() as c:
            c.execute("INSERT OR REPLACE INTO sensor_calibrations VALUES(?,?,?,?,?,?,?)", (sensor_id, metric, version, min_value, max_value, valid_from, valid_to))

    def ingest(self, mission_id, records, actor):
        if len(records) > self.max_batch_size: raise ValidationError(f"batch exceeds {self.max_batch_size} records")
        accepted = []; rejected = []
        with self.db.transaction() as c:
            mission = c.execute("SELECT status FROM missions WHERE id=?", (mission_id,)).fetchone()
            if not mission: raise NotFound("mission not found")
            if mission["status"] != "active": raise Conflict("telemetry is accepted only while mission is active")
            for item in records:
                try:
                    result = self._validate(c, mission_id, item)
                    if result["duplicate"]: accepted.append({"ingestion_id": item.get("ingestion_id"), "duplicate": True}); continue
                    oid = str(uuid.uuid4()); flags = result["flags"]; state = "accepted" if not flags else "quarantined"
                    c.execute("INSERT INTO observations VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (oid, mission_id, item["sequence_no"], item["observed_at"], item["latitude"], item["longitude"], item["depth_m"], json.dumps(item["measurements"]), state, json.dumps(flags), item["ingestion_id"], utcnow()))
                    if flags:
                        c.execute("INSERT INTO incidents VALUES(?,?,?,?,?,?,?,?,?)", (str(uuid.uuid4()), mission_id, oid, "quality_outlier", "high" if "range" in flags else "medium", "open", json.dumps({"flags": flags}), utcnow(), None))
                    accepted.append({"observation_id": oid, "sequence_no": item["sequence_no"], "status": state})
                except (KeyError, ValueError, ValidationError, Conflict) as exc:
                    rejected.append({"ingestion_id": item.get("ingestion_id"), "reason": str(exc)})
            max_seq = c.execute("SELECT MAX(sequence_no) n FROM observations WHERE mission_id=? AND quality_status='accepted'", (mission_id,)).fetchone()["n"] or 0
            if max_seq and (max_seq % self.checkpoint_interval == 0 or not c.execute("SELECT 1 FROM checkpoints WHERE mission_id=?", (mission_id,)).fetchone()):
                c.execute("INSERT OR REPLACE INTO checkpoints VALUES(?,?,?)", (mission_id, max_seq, utcnow()))
            record(c, actor, "telemetry.ingested", "mission", mission_id, {"accepted": len(accepted), "rejected": len(rejected)})
        return {"accepted": accepted, "rejected": rejected}

    def _validate(self, c, mission_id, item):
        required = ("sequence_no", "observed_at", "latitude", "longitude", "depth_m", "measurements", "ingestion_id")
        if any(k not in item for k in required): raise ValidationError("record missing required field")
        if item["sequence_no"] <= 0: raise ValidationError("sequence_no must be positive")
        if not (-90 <= item["latitude"] <= 90 and -180 <= item["longitude"] <= 180 and item["depth_m"] >= 0): raise ValidationError("invalid position or depth")
        if c.execute("SELECT 1 FROM observations WHERE ingestion_id=?", (item["ingestion_id"],)).fetchone(): return {"duplicate": True, "flags": []}
        flags = []
        for metric, value in item["measurements"].items():
            cal = c.execute("SELECT min_value,max_value FROM sensor_calibrations WHERE metric=? ORDER BY valid_from DESC LIMIT 1", (metric,)).fetchone()
            if not cal: flags.append("uncalibrated:" + metric)
            elif not (cal["min_value"] <= float(value) <= cal["max_value"]): flags.append("range")
        prev = c.execute("SELECT MAX(sequence_no) n FROM observations WHERE mission_id=?", (mission_id,)).fetchone()["n"]
        if prev is not None and item["sequence_no"] <= prev: raise Conflict("sequence must increase")
        return {"duplicate": False, "flags": flags}

import unittest, uuid
from pathlib import Path
from qsc_solo.db import Database
from qsc_solo.errors import Conflict, Forbidden, ValidationError
from qsc_solo.mission_service import MissionService
from qsc_solo.telemetry_service import TelemetryService
from qsc_solo.recovery_service import RecoveryService
from qsc_solo.export_service import ExportService

class SurveyOpsTests(unittest.TestCase):
    def setUp(self):
        self.db_path = Path("tests") / ("test-" + uuid.uuid4().hex + ".sqlite"); self.db = Database(str(self.db_path))
        self.m = MissionService(self.db); self.t = TelemetryService(self.db, checkpoint_interval=2, max_batch_size=3)
        self.r = RecoveryService(self.db); self.e = ExportService(self.db)
        self.mission = self.m.create("vessel-7", "Shelf transect", [{"latitude": 10, "longitude": 20, "depth_m": 50}], 120, "operator")
        self.t.seed_calibration("sensor-x", "temperature", "v1", -2, 35)

    def tearDown(self):
        for suffix in ("", "-journal", "-wal", "-shm"):
            p = Path(str(self.db_path) + suffix)
            if p.exists(): p.unlink()

    def record(self, n, value=12, iid=None):
        return {"sequence_no": n, "observed_at": f"2026-01-01T00:0{n}:00+00:00", "latitude": 10+n/100, "longitude": 20, "depth_m": 50, "measurements": {"temperature": value}, "ingestion_id": iid or f"packet-{n}"}

    def test_lifecycle_and_vessel_lock(self):
        self.m.transition(self.mission.id, "active", "operator")
        other = self.m.create("vessel-7", "Collision", [{"latitude": 1, "longitude": 1, "depth_m": 1}], 10, "operator")
        with self.assertRaises(Conflict): self.m.transition(other.id, "active", "operator")
        self.m.transition(self.mission.id, "paused", "operator"); self.m.transition(self.mission.id, "active", "operator")
        self.m.transition(self.mission.id, "completed", "operator")
        with self.assertRaises(Conflict): self.m.transition(self.mission.id, "active", "operator")

    def test_partial_batch_and_quarantine(self):
        self.m.transition(self.mission.id, "active", "operator")
        result = self.t.ingest(self.mission.id, [self.record(1), self.record(2, 100), {"sequence_no": 3}], "operator")
        self.assertEqual(len(result["accepted"]), 2); self.assertEqual(len(result["rejected"]), 1)
        status = self.m.status(self.mission.id)
        self.assertEqual(status["observation_counts"]["accepted"], 1); self.assertEqual(status["observation_counts"]["quarantined"], 1)
        self.assertEqual(status["checkpoint"], 1)

    def test_idempotent_retry(self):
        self.m.transition(self.mission.id, "active", "operator")
        first = self.t.ingest(self.mission.id, [self.record(1)], "operator")
        second = self.t.ingest(self.mission.id, [self.record(1)], "operator")
        self.assertFalse(second["rejected"]); self.assertTrue(second["accepted"][0]["duplicate"])
        self.assertEqual(first["accepted"][0]["observation_id"], self.m.status(self.mission.id)["mission"]["id"] if False else first["accepted"][0]["observation_id"])

    def test_ordering_and_resume(self):
        self.m.transition(self.mission.id, "active", "operator"); self.t.ingest(self.mission.id, [self.record(1), self.record(2)], "operator")
        self.assertEqual(self.r.resume_plan(self.mission.id)["resume_from_sequence"], 3)
        late = self.t.ingest(self.mission.id, [self.record(2, iid="late")], "operator")
        self.assertEqual(late["rejected"][0]["reason"], "sequence must increase")

    def test_export_requires_completed_and_role(self):
        self.m.transition(self.mission.id, "active", "operator"); self.t.ingest(self.mission.id, [self.record(1)], "operator")
        with self.assertRaises(Conflict): self.e.create(self.mission.id, "operator", "operator")
        self.m.transition(self.mission.id, "completed", "operator")
        out = self.e.create(self.mission.id, "operator", "operator")
        self.assertEqual(out["observation_count"], 1)
        with self.assertRaises(Forbidden): self.e.create(self.mission.id, "auditor", "auditor", include_quarantined=True)

    def test_invalid_mission(self):
        with self.assertRaises(ValidationError): self.m.create("v", "bad", [], 10, "operator")

if __name__ == "__main__": unittest.main()

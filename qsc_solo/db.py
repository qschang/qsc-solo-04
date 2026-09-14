import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS missions(
 id TEXT PRIMARY KEY, vessel_id TEXT NOT NULL, name TEXT NOT NULL, status TEXT NOT NULL,
 max_duration_min INTEGER NOT NULL, transects_json TEXT NOT NULL, created_by TEXT NOT NULL,
 version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS observations(
 id TEXT PRIMARY KEY, mission_id TEXT NOT NULL REFERENCES missions(id), sequence_no INTEGER NOT NULL,
 observed_at TEXT NOT NULL, latitude REAL NOT NULL, longitude REAL NOT NULL, depth_m REAL NOT NULL,
 measurements_json TEXT NOT NULL, quality_status TEXT NOT NULL, quality_flags_json TEXT NOT NULL,
 ingestion_id TEXT NOT NULL UNIQUE, received_at TEXT NOT NULL, UNIQUE(mission_id, sequence_no));
CREATE TABLE IF NOT EXISTS sensor_calibrations(
 sensor_id TEXT NOT NULL, metric TEXT NOT NULL, version TEXT NOT NULL, min_value REAL NOT NULL,
 max_value REAL NOT NULL, valid_from TEXT NOT NULL, valid_to TEXT, PRIMARY KEY(sensor_id, metric, version));
CREATE TABLE IF NOT EXISTS checkpoints(mission_id TEXT PRIMARY KEY REFERENCES missions(id), last_sequence INTEGER NOT NULL, saved_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS incidents(id TEXT PRIMARY KEY, mission_id TEXT NOT NULL REFERENCES missions(id), observation_id TEXT,
 kind TEXT NOT NULL, severity TEXT NOT NULL, state TEXT NOT NULL, details_json TEXT NOT NULL, opened_at TEXT NOT NULL, resolved_at TEXT);
CREATE TABLE IF NOT EXISTS exports(id TEXT PRIMARY KEY, mission_id TEXT NOT NULL REFERENCES missions(id), requested_by TEXT NOT NULL,
 include_quarantined INTEGER NOT NULL, observation_count INTEGER NOT NULL, content_hash TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit_events(id INTEGER PRIMARY KEY AUTOINCREMENT, actor TEXT NOT NULL, action TEXT NOT NULL,
 entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, detail_json TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS vessel_locks(vessel_id TEXT PRIMARY KEY, mission_id TEXT NOT NULL, acquired_at TEXT NOT NULL);
"""

class _ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc, tb):
        try:
            return super().__exit__(exc_type, exc, tb)
        finally:
            self.close()

class Database:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self):
        conn = sqlite3.connect(self.path, timeout=10, isolation_level=None, factory=_ClosingConnection)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def initialize(self):
        with self.connect() as conn: conn.executescript(SCHEMA)

    @contextmanager
    def transaction(self):
        conn = self.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally: conn.close()

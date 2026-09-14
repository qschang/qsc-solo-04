import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from .config import Settings
from .db import Database
from .errors import DomainError, Forbidden, NotFound, ValidationError, Conflict
from .mission_service import MissionService
from .telemetry_service import TelemetryService
from .recovery_service import RecoveryService
from .export_service import ExportService

class App:
    def __init__(self, settings=None):
        self.settings = settings or Settings.from_env(); self.db = Database(self.settings.database_path)
        self.missions = MissionService(self.db); self.telemetry = TelemetryService(self.db, self.settings.checkpoint_interval, self.settings.max_batch_size)
        self.recovery = RecoveryService(self.db); self.exports = ExportService(self.db)

class Handler(BaseHTTPRequestHandler):
    app = None
    def _send(self, status, body):
        raw = json.dumps(body, default=str).encode(); self.send_response(status); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def _body(self): return json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")
    def _role(self): return self.headers.get("X-Role", "operator")
    def _error(self, exc):
        status = 403 if isinstance(exc, Forbidden) else 404 if isinstance(exc, NotFound) else 400 if isinstance(exc, (ValidationError, ValueError, json.JSONDecodeError)) else 409
        return self._send(status, {"error": str(exc)})
    def do_GET(self):
        path = urlparse(self.path).path
        try:
            if path == "/health": return self._send(200, {"status":"ok"})
            if path.startswith("/missions/") and path.endswith("/status"):
                return self._send(200, self.app.missions.status(path.split("/")[2]))
            if path.startswith("/missions/") and path.endswith("/resume-plan"):
                return self._send(200, self.app.recovery.resume_plan(path.split("/")[2]))
            return self._send(404, {"error":"not found"})
        except (DomainError, ValueError) as e: return self._error(e)
    def do_POST(self):
        path = urlparse(self.path).path; role = self._role()
        try:
            data = self._body()
            if path == "/missions": return self._send(201, self.app.missions.create(data.get("vessel_id"), data.get("name"), data.get("transects"), int(data.get("max_duration_min", 0)), role).__dict__)
            if path.startswith("/missions/"):
                parts = path.strip("/").split("/"); mid = parts[1]
                if parts[-1] in {"start","pause","resume","complete","abort"}: return self._send(200, self.app.missions.transition(mid, {"start":"active","pause":"paused","resume":"active","complete":"completed","abort":"aborted"}[parts[-1]], role).__dict__)
                if parts[-1] == "observations": return self._send(200, self.app.telemetry.ingest(mid, data.get("records", []), role))
                if parts[-1] == "checkpoint": return self._send(200, {"last_sequence": self.app.recovery.checkpoint(mid, role)})
                if parts[-1] == "exports": return self._send(201, self.app.exports.create(mid, role, role, bool(data.get("include_quarantined", False))))
            return self._send(404, {"error":"not found"})
        except (DomainError, ValueError) as e: return self._error(e)

def main():
    app = App(); Handler.app = app; server = ThreadingHTTPServer((app.settings.bind_host, app.settings.bind_port), Handler); print(f"surveyops listening on http://{app.settings.bind_host}:{app.settings.bind_port}"); server.serve_forever()

if __name__ == "__main__": main()

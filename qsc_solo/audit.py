import json
from .models import utcnow

def record(conn, actor: str, action: str, entity_type: str, entity_id: str, detail: dict):
    conn.execute("INSERT INTO audit_events(actor,action,entity_type,entity_id,detail_json,created_at) VALUES(?,?,?,?,?,?)",
                 (actor, action, entity_type, entity_id, json.dumps(detail, sort_keys=True), utcnow()))

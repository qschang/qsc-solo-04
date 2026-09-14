from .errors import Forbidden

ROLE_PERMISSIONS = {
    "operator": {"mission:write", "telemetry:write", "export:write", "mission:read"},
    "scientist": {"mission:read", "telemetry:write", "export:write"},
    "auditor": {"mission:read", "audit:read", "export:read"},
}

def require(role: str, permission: str):
    if permission not in ROLE_PERMISSIONS.get(role, set()):
        raise Forbidden(f"role {role!r} cannot perform {permission}")

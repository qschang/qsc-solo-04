# Architecture and evidence map

## Modules

- `mission_service`: validates transects, manages the mission state machine, and enforces one-active-mission-per-vessel.
- `telemetry_service`: validates packet shape, calibration ranges, strict sequence order, idempotent retries, partial batch outcomes, checkpoints, and quality incidents.
- `recovery_service`: turns persisted checkpoints into an operator-visible resume plan.
- `export_service`: role-gated completion export with quarantined-data policy and content hash.
- `db`, `audit`, `auth`, `api`: transactional persistence, immutable audit trail, permission checks, and HTTP boundary.

## Distinct data flows

1. **Mission launch:** JSON mission request → coordinate/duration validation → `planned` row → vessel lock on `active` → audit event → status endpoint.
2. **Telemetry quality:** packet batch → schema/position/calibration/ordering checks → accepted or quarantined observation rows → incident rows for flags → checkpoint update → per-record response showing partial failures.
3. **Recovery:** persisted accepted sequence → checkpoint query → resume plan with next sequence; pause/resume transitions release and reacquire vessel locks.
4. **Scientific export:** completed mission + role policy → accepted-only or explicit scientist-approved quarantined selection → deterministic JSON projection → SHA-256 export record and audit event.

## Failure and recovery semantics

Malformed records do not roll back valid records in the same batch. Duplicate packet IDs return a duplicate acknowledgement and do not create a second observation. Out-of-order packets are rejected to preserve temporal meaning. A process restart loses no committed observation or checkpoint because all writes use SQLite transactions. Invalid state transitions, vessel conflicts, incomplete exports, and forbidden role combinations are user-visible errors.

## Extension boundary

The persisted calibration table, incident table, checkpoint table, and export manifest are intentionally separate seams for adding sensor-specific calibration versions, incident acknowledgement workflows, mission geofences, resumable file streaming, retention policies, and concurrency-aware ingestion without flattening the domain into generic CRUD.

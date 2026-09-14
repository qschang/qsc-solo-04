# qsc-solo-04 — AquaSentinel Survey Operations

AquaSentinel is a small but real mission-operations core for autonomous oceanographic surveys. It tracks vessel missions, ingests timestamped sensor packets, quarantines out-of-range observations, checkpoints progress for restart, and produces hash-addressed exports for downstream science workflows.

## Domain

- **Business area:** autonomous ocean survey operations and observation-quality provenance.
- **Users:** vessel operators, field scientists, and data auditors.
- **Core flow:** define a transect mission → reserve a vessel and launch it → ingest ordered telemetry in retryable batches → validate against calibration bounds and open quality incidents → pause/resume from a durable checkpoint → complete and export an auditable dataset.

The system deliberately keeps a quarantined observation visible without silently mixing it into the accepted scientific export. Vessel locking prevents two active missions from claiming the same platform. Every state-changing action is written to an audit log.

## Running

Python 3.11+ and the standard library are enough.

```powershell
python -m unittest discover -s tests -v
python -m qsc_solo.api
```

Configuration is environment-based: `SURVEYOPS_DB`, `SURVEYOPS_HOST`, `SURVEYOPS_PORT`, `SURVEYOPS_MAX_BATCH`, and `SURVEYOPS_CHECKPOINT_INTERVAL`.

Example API calls:

```powershell
Invoke-RestMethod http://127.0.0.1:8080/health
Invoke-RestMethod -Method Post http://127.0.0.1:8080/missions -Headers @{"X-Role"="operator"} -ContentType application/json -Body '{"vessel_id":"vessel-7","name":"Shelf transect","max_duration_min":120,"transects":[{"latitude":10,"longitude":20,"depth_m":50}]}'
```

## Design notes

SQLite transactions provide atomic batch handling and a durable recovery point without requiring an external service. Ingestion is idempotent by packet ID, but sequence order remains strict so late packets are rejected instead of rewriting the scientific timeline. Exports are SHA-256 addressed and role-gated; only scientists may explicitly include quarantined data.

See `docs/architecture.md` for module boundaries, data-flow evidence, and extension directions.

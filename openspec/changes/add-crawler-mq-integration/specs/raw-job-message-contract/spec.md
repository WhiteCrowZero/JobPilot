## ADDED Requirements

### Requirement: Versioned raw job collection message
The system SHALL define one strict, JSON-serializable V1 contract for messages with `event_type` equal to `job.raw.collected`. A message MUST contain `schema_version=1`, a UUID `message_id`, a UUID `trace_id`, `producer`, timezone-aware `produced_at`, `source_platform`, `raw_payload`, and at least one of `external_job_id` or `source_url`; it MAY contain timezone-aware `fetched_at`.

#### Scenario: Valid simulator message is accepted
- **WHEN** the simulator sends a V1 message with all required fields and JSON-only raw payload values
- **THEN** the Worker validates it as a `job.raw.collected` message before ingestion begins

#### Scenario: Unsupported contract is rejected without retry
- **WHEN** the Worker receives a message with an unsupported schema version, event type, missing required identity field, or non-JSON payload value
- **THEN** it SHALL classify the delivery as a non-retryable contract failure and SHALL not invoke the normalizer

### Requirement: Backend-owned source registration
The backend SHALL map `source_platform` to its registered source name, base URL, and adapter. Producers MUST NOT control those backend-owned values, and unsupported source platforms SHALL be treated as non-retryable business failures.

#### Scenario: Registered platform resolves to backend source
- **WHEN** a valid message names a registered source platform
- **THEN** ingestion SHALL use that platform's backend-owned source configuration and adapter

#### Scenario: Unknown platform is not retried
- **WHEN** a validly shaped message names an unregistered source platform
- **THEN** the Worker SHALL record a diagnosable permanent failure without scheduling a retry

### Requirement: Stable event and trace identity semantics
The producer SHALL retain `message_id` and `trace_id` for Celery redelivery of the same business event. It MUST generate a new `message_id` when the source job content changes, while preserving the trace identity through retries within that collection flow.

#### Scenario: Redelivery retains message identity
- **WHEN** Celery retries a delivery after a transient failure
- **THEN** the retried task SHALL use the original message ID and trace ID

#### Scenario: Changed source content creates a new event
- **WHEN** the producer detects changed content for a source job using its URL, external ID, or canonical content identity
- **THEN** it SHALL send a new event with a new message ID

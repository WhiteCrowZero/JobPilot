## ADDED Requirements

### Requirement: RabbitMQ-routed single ingestion task
The system SHALL use RabbitMQ as the Celery broker and Redis as the Celery result backend. It SHALL declare `job.ingestion` and `default` queues and route task `job.import_raw` to `job.ingestion`; the initial implementation MUST keep raw import and skill synchronization within this one Celery task.

#### Scenario: Imported task reaches the ingestion queue
- **WHEN** a producer sends task `job.import_raw`
- **THEN** Celery SHALL route it to `job.ingestion` for a configured Worker to consume

#### Scenario: Unrouted task uses the default queue
- **WHEN** a Celery task has no explicit route
- **THEN** it SHALL use the configured `default` queue

### Requirement: Two-transaction durable import orchestration
The import task SHALL first commit raw-record, normalized job-post, and job-detail processing, then perform skill synchronization in a separate transaction. The second transaction MUST reload the raw record by persisted ID and reconstruct skill candidates from its stored raw payload through the source adapter; it MUST NOT depend on in-memory candidates returned by a prior attempt.

#### Scenario: First delivery completes both transactions
- **WHEN** a valid, previously unseen raw job message is consumed
- **THEN** the task SHALL commit raw/job data before committing the corresponding job-skill synchronization

#### Scenario: Retry recovers after skill synchronization failure
- **WHEN** raw/job data committed but skill synchronization fails with a retryable infrastructure error
- **THEN** a retry SHALL reuse the persisted raw record and reconstruct its skill candidates before reattempting synchronization

### Requirement: Idempotent duplicate delivery handling
The system SHALL treat a repeated `message_id` as an idempotent delivery and a distinct message with identical `source_id + raw_content_hash` as duplicate raw content. These paths MUST avoid duplicate raw/job creation while retaining enough persisted state to complete or confirm skill synchronization; business fingerprint upsert SHALL remain the final normalized-job deduplication layer.

#### Scenario: Same message is delivered twice
- **WHEN** the Worker receives a second delivery with the same message ID
- **THEN** it SHALL not create another raw record or job post and SHALL be able to complete idempotent skill synchronization from the existing record

#### Scenario: Different message has duplicate raw content
- **WHEN** the Worker receives a new message ID whose source and raw-content hash already exist
- **THEN** it SHALL update only the allowed seen metadata and SHALL not duplicate normalized data

### Requirement: Classified retry and failure behavior
The Worker SHALL retry only explicitly classified transient infrastructure failures with bounded exponential backoff and jitter. Contract failures, unsupported source/adapter failures, duplicate deliveries, and unmatched skills MUST NOT be retried. Final failures MUST retain diagnosable persisted state, and structured logs MUST include correlation identifiers without logging complete raw payloads.

#### Scenario: Temporary database failure is retried
- **WHEN** a whitelisted transient database connectivity, timeout, or deadlock error occurs
- **THEN** Celery SHALL retry the task using the configured bounded backoff policy

#### Scenario: Unmatched skill completes normally
- **WHEN** skill extraction yields candidates that have no dictionary alias matches
- **THEN** the task SHALL complete without retry and record the unmatched result according to the skill-sync result contract

### Requirement: Celery is the sole queue abstraction for raw job ingestion
The raw job ingestion path SHALL use Celery publish and consume semantics directly and SHALL NOT route collection messages through the Redis List `MessageQueue` or `DomainEvent` abstraction.

#### Scenario: Producer publishes without a generic queue wrapper
- **WHEN** the simulator emits a raw-job event
- **THEN** it SHALL use Celery task dispatch by the stable task name rather than a Redis List queue API

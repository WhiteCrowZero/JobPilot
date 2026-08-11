## ADDED Requirements

### Requirement: Database-independent simulator producer
The project SHALL provide a standalone simulator process that reads the Celery broker configuration and message contract, creates no database session, and dispatches `job.import_raw` by Celery `send_task`.

#### Scenario: Simulator sends a job without importing Worker task code
- **WHEN** a developer runs the simulator with a valid sample message and reachable broker
- **THEN** it SHALL send `job.import_raw` without importing the Worker task function or opening a database connection

### Requirement: Reproducible local integration procedure
The project SHALL document a Windows-friendly procedure to start PostgreSQL, Redis, RabbitMQ, migrations, Worker, and simulator, and to verify the message's raw record, normalized job, and job-skill outcomes. The procedure MUST use `127.0.0.1` addresses in local examples.

#### Scenario: Developer verifies one end-to-end import
- **WHEN** the documented infrastructure, Worker, and simulator steps are followed
- **THEN** the developer can observe a consumed task and verify that its raw record, job post, and synchronized skills were persisted

### Requirement: Simulator supports idempotency and recovery demonstrations
The simulator or its documented fixtures SHALL make it possible to send an identical event again, send a new message with identical raw content, and send changed content for the same source job so the integration path can demonstrate the intended idempotency semantics.

#### Scenario: Duplicate and changed fixtures show distinct behavior
- **WHEN** a developer runs the documented duplicate and changed-content samples
- **THEN** the duplicate samples SHALL not create duplicate data and the changed-content sample SHALL be processed as a new event subject to normalized fingerprint upsert

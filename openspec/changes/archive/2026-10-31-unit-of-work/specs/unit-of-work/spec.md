# unit-of-work Specification

## Purpose

Provide an asynchronous Unit of Work that groups repositories over a single database session, commits on successful exit, rolls back on exception, and never closes the session it did not create.

## ADDED Requirements

### Requirement: UoW commits on success
The system SHALL provide an async context manager `UnitOfWork` over an injected `AsyncSession`; on normal exit it SHALL call `commit()` exactly once.

#### Scenario: success commits
- **WHEN** a block using `async with uow:` completes without exception
- **THEN** `session.commit()` is invoked once and persisted changes are visible

### Requirement: UoW rolls back on exception
On exception, the UoW SHALL call `rollback()` and re-raise the exception.

#### Scenario: exception rolls back
- **WHEN** an exception is raised inside the block
- **THEN** `session.rollback()` is invoked and no partial writes persist

### Requirement: session stays open after exit
The UoW SHALL NOT close the session; ownership remains with `get_session`.

#### Scenario: session open after exit
- **WHEN** the block exits (success or failure)
- **THEN** the session remains open and usable

### Requirement: business exception leaves no partial writes
A business-rule exception raised mid-block SHALL leave the database unchanged.

#### Scenario: partial writes reverted
- **WHEN** an `AppError` is raised after some `add`/`flush` calls
- **THEN** none of those flushed changes are committed

### Requirement: one UoW per request
`get_uow()` SHALL construct a distinct UoW per request over the injected session.

#### Scenario: services do not share UoW
- **WHEN** two concurrent requests execute
- **THEN** each uses its own UoW instance and session

### Requirement: repositories only flush
Repositories exposed by the UoW SHALL only `flush()`; `commit()` is owned by the UoW.

#### Scenario: add does not commit
- **WHEN** `uow.<repo>.add()` is called inside a block
- **THEN** the row is visible within the session but not committed until exit

### Requirement: sub-UoW only for independent audit
A sub-UoW SHALL be permitted only for independent audit writes (`intento_acceso`); it SHALL NOT be used for domain writes.

#### Scenario: audit sub-UoW commits independently
- **WHEN** an audit write uses a separate UoW/session
- **THEN** it commits even if the outer domain transaction rolls back

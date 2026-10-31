# Spec Delta

## Purpose

Provide a shared, generic repository abstraction for asynchronous data access with explicit eager loading and flush-only writes, plus concrete identity/audit repositories, without changing HTTP contracts.

## ADDED Requirements

### Requirement: BaseRepository generic CRUD with flush-not-commit
The system SHALL provide a generic `BaseRepository[T]` over an injected `AsyncSession` exposing `get_by_id`, `get_all`, `count`, `add`, `update`, and `delete`; `add` and `update` SHALL execute `flush()` and SHALL never call `commit()`.

#### Scenario: add does not commit
- **WHEN** `add()` is invoked within a session
- **THEN** the row is visible inside the same session but not after rollback of the external transaction

#### Scenario: get_by_id returns entity
- **WHEN** an entity with the given id exists
- **THEN** `get_by_id` returns it

#### Scenario: get_all supports filtering
- **WHEN** `get_all` is called
- **THEN** it returns the matching entities with explicit precarga of relationships

### Requirement: SoftDeleteRepository filtering
The system SHALL provide `SoftDeleteRepository[T]` that filters `borrado_en IS NULL` by default and adds `get_by_id_including_deleted` and `soft_delete()`.

#### Scenario: soft-deleted excluded from listing
- **WHEN** an entity is soft-deleted
- **THEN** it is excluded from `get_all` and `get_by_id`

#### Scenario: get_by_id_including_deleted finds soft-deleted
- **WHEN** a soft-deleted entity is queried via `get_by_id_including_deleted`
- **THEN** it is returned

### Requirement: Explicit selectinload on aggregates
Every repository method returning an aggregate with relationships SHALL use explicit `selectinload` and SHALL NOT trigger lazy loading.

#### Scenario: no N+1 on listing
- **WHEN** a listing with relationships is executed under a query counter
- **THEN** the number of queries stays constant regardless of item count

### Requirement: Typed constructors over AsyncSession
Pilot repositories `UsuarioRepository`, `AsignacionRolRepository`, `IntentoAccesoRepository`, and `EventoSeguridadRepository` SHALL accept a typed `AsyncSession` in their constructor.

#### Scenario: construction with session
- **WHEN** a repository is constructed with an `AsyncSession`
- **THEN** it can perform its operations against that session

### Requirement: Refactor preserves HTTP contracts
Refactoring `app/modules/usuarios` to consume the repositories SHALL NOT change HTTP contracts, response codes, or observable behavior.

#### Scenario: full suite green
- **WHEN** the test suite runs after refactor
- **THEN** all existing tests pass with identical status codes

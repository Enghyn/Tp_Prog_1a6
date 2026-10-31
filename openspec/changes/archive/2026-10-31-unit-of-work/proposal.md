# Proposal

## Why

There is no transactional boundary abstraction: services in `app/modules/usuarios` open their own `async with sesion.begin()` blocks on dedicated sessions, so writes can be partial, there is no single commit/rollback point, and service code is coupled to session lifecycle. This change introduces a `UnitOfWork` async context manager over a single injected session, plus a `get_uow` FastAPI dependency, and migrates `usuarios` to it, establishing the pattern for C-15+ modules.

## What Changes

- Add `app/core/unit_of_work.py` with a `UnitOfWork` async context manager exposing repositories as properties; `__aexit__` commits on success and rolls back on exception; it never closes the session (owned by `get_session`).
- Add `get_uow()` dependency: one UoW per request built over the injected session.
- Add `app/modules/usuarios/unit_of_work.py` as the reference module-level UoW exposing the identity/audit repositories.
- Document the sub-UoW rule: allowed only for independent audit (`intento_acceso`), never for domain writes.
- Refactor `app/modules/usuarios/service.py` to use the UoW instead of dedicated `sesion.begin()` blocks; update `TODO(C-14)` markers.
- No HTTP contract changes, no migration, no new endpoints.

## Capabilities

### New Capabilities
- `unit-of-work`: asynchronous Unit of Work grouping repositories over a single session with commit-on-success/rollback-on-exception semantics, per-request dependency, module-level reference implementation, and documented sub-UoW audit rule.

### Modified Capabilities
- `repositorios`: `add`/`update` remain flush-only; the UoW becomes the single commit owner for a module.

## Impact

- Affected code: `app/core/`, `app/modules/usuarios/`, `tests/`.
- No API changes; existing 295 tests must remain green.
- Depends on C-13 `repositories` (archived). Governance: CRITICO.

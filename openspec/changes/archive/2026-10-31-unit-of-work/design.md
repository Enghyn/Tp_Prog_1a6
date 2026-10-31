# Design

## Context

C-13 introduced generic repositories that only `flush()`. There is no transaction owner; `usuarios` services open dedicated `async with sesion.begin()` blocks, coupling business logic to session lifecycle and risking partial writes. C-14 introduces the missing transactional boundary.

## Decisions

1. **UoW as async context manager only.** `UnitOfWork.__aenter__` returns self; `__aexit__(exc_type,...)` calls `commit()` if `exc_type is None` else `rollback()`, then re-raises. It never closes the session.
2. **Session injection.** `get_uow()` is a FastAPI dependency that depends on `get_session()` and constructs `UnitOfWork(session)`. One UoW per request; services receive it via `Depends`.
3. **Repository exposure via properties.** Module UoW (`app/modules/usuarios/unit_of_work.py`) exposes `usuarios`, `asignaciones_rol`, `intentos_acceso`, `eventos_seguridad` as lazy properties constructing the concrete repositories over the shared session.
4. **Core UoW is generic.** `app/core/unit_of_work.py` defines a base `UnitOfWork` accepting an `AsyncSession` and an optional mapping of repository factories; module UoWs subclass it.
5. **Migration strategy (incremental).** Replace `async with sesion_admin.begin()` call sites in `service.py` with `async with self.uow:`; keep `obtener_sesion_*` helpers as thin wrappers delegating to UoW where still needed for audit sub-transactions; remove `TODO(C-14)` markers.
6. **Sub-UoW rule.** Only `intento_acceso` audit writes may use an independent UoW/session (so a failed login still records the attempt). Domain writes MUST share the request UoW. Documented in AGENTS.md and the module docstring.
7. **Exception propagation.** UoW does not swallow exceptions; rollback then re-raise, preserving `AppError` mapping in handlers.
8. **Interaction with test fixture.** The `contexto_auth` fixture wraps tests in an outer transaction + savepoint; UoW's `commit()` inside a savepoint is safe because SQLAlchemy emits a savepoint commit, leaving the outer rollback intact. UoW must not call `session.close()`.

## Risks / Trade-offs

- Refactor blast radius on C-09/C-12 services; mitigated by keeping HTTP contracts and running the full suite.
- Transaction nesting with the test fixture: verified by tests (rollback leaves DB intact).
- Audit sub-UoW independence requires a separate session factory; reuse existing `obtener_sesion_auditoria`.

## Non-goals

- No changes to other modules (C-15+).
- No migration, no new endpoints.
- No Celery/Redis.

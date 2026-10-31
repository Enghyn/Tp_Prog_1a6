# Tasks

## 1. Safety net
- [x] 1.1 Run full suite baseline: `pytest -q` → 295 passed. Record commit hash.

## 2. Core UoW (TDD)
- [x] 2.1 Write `tests/test_unit_of_work.py` RED: commit on success, rollback on exception, session stays open, business exception no partial writes, distinct UoWs per request.
- [x] 2.2 Implement `app/core/unit_of_work.py` (`UnitOfWork` async context manager) GREEN.
- [x] 2.3 Implement `get_uow()` dependency in `app/core/dependencies.py` GREEN.
- [x] 2.4 Verify: `pytest tests/test_unit_of_work.py -q`.

## 3. Module UoW (TDD)
- [x] 3.1 Implement `app/modules/usuarios/unit_of_work.py` exposing repos as properties.
- [x] 3.2 Update `app/modules/usuarios/service.py`: replace `async with sesion.begin()` with `async with self.uow:`; remove `TODO(C-14)` markers.
- [x] 3.3 Keep `obtener_sesion_*` as thin audit wrappers where needed.

## 4. Sub-UoW rule documentation
- [x] 4.1 Document sub-UoW rule in `AGENTS.md` and module docstring.

## 5. Verification
- [x] 5.1 Run full suite: `pytest -q` → all green, no warnings about open sessions.
- [x] 5.2 Verify HTTP contracts unchanged: response codes identical (covered by suite).
- [x] 5.3 Run `alembic check` → clean (no new migration expected).
- [x] 5.4 Run `openspec validate unit-of-work --strict`.

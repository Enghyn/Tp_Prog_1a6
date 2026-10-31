# Tasks

## 1. Safety net baseline

- [x] 1.1 Run full pytest suite and record baseline (287 passed) before touching code; verify `pytest` exits 0

## 2. Generic repository hierarchy

- [x] 2.1 Create `app/core/repository.py` with `BaseRepository[T]` (get_by_id, get_all, count, add, update, delete); add/flush tests; verify `pytest tests/test_repository_base.py` passes
- [x] 2.2 Add `SoftDeleteRepository[T]` (borrado_en IS NULL filter, get_by_id_including_deleted, soft_delete); verify `pytest tests/test_repository_soft_delete.py` passes
- [x] 2.3 Implement selectinload strategy in base methods; verify query-counter test shows no N+1

## 3. Pilot repositories

- [x] 3.1 Implement `UsuarioRepository`, `AsignacionRolRepository`, `IntentoAccesoRepository`, `EventoSeguridadRepository` with typed AsyncSession constructor; verify unit tests pass
- [x] 3.2 Add tests for typed constructors and basic CRUD; verify `pytest tests/test_repositories_pilot.py` passes

## 4. Refactor usuarios module

- [x] 4.1 Migrate data-access functions in `app/modules/usuarios/repository.py` to repository classes (keep session-factory deps); verify imports resolve
- [x] 4.2 Update `service.py` to consume repositories; verify no leftover raw SQL access
- [x] 4.3 Run full suite; verify HTTP contracts/response codes unchanged (287+ tests pass)

## 5. Test evidence

- [x] 5.1 Add query-counter test demonstrating precarga (no N+1); verify passes
- [x] 5.2 Add test that `add` does not commit (visible only after external commit); verify passes
- [x] 5.3 Add soft-delete test (excluded from listing, found via including_deleted); verify passes

## 6. Final verification

- [x] 6.1 Run `alembic check` and verify clean (no pending ops)
- [x] 6.2 Run full pytest suite; verify all pass

## Workflow follow-up

- Archive the change after review requirements are satisfied.
- Verify the archived result.

# Design

## Context

See proposal.md — Why. Existing data access lives in `app/modules/usuarios/repository.py` as free functions mixed with FastAPI session-factory dependencies. Models use `lazy="raise"` and partial unique indexes.

## Goals / Non-Goals

**Goals:**
- Introduce `BaseRepository[T]` and `SoftDeleteRepository[T]` in `app/core/repository.py`.
- Provide 4 pilot repositories for identity/audit models.
- Refactor `app/modules/usuarios` to consume repositories without changing HTTP contracts.

**Non-Goals:**
- Unit of Work (C-14).
- Repositories for other modules (C-15/C-16).
- No Alembic migration.

## Decisions

1. **Generic[T] with TypeVar bound to SQLModel** — enables typed `get_by_id`/`get_all` without per-model code. Alternative: per-model base classes — rejected (duplication).

2. **AsyncSession injection via constructor** — repositories never create/close sessions; session lifecycle stays with `get_session`. Alternative: session factory — rejected (couples to request scope).

3. **flush-only** — `add`/`update` call `flush()`; commit remains external (UoW later). Alternative: commit inside repo — rejected (violates RN-02/transactional atomicity).

4. **Soft-delete field name `borrado_en`** — matches domain models (`Vehiculo`, `Repuesto`). Pilot identity models do not soft-delete; `SoftDeleteRepository` is exercised via tests on domain models or a test fixture. Alternative: `deleted_at` — rejected (inconsistent with KB/model).

5. **selectinload strategy** — each aggregate-returning method explicitly `selectinload`s needed relations; avoids N+1 and lazy loading.

6. **Incremental migration** — service functions keep dedicated-session dependencies (`obtener_sesion_auditoria`, etc.) untouched; data-access functions migrate to repository classes. Avoids breaking the audit-session pattern until C-14.

## Risks / Trade-offs

- [Refactor blast radius] → keep HTTP contract tests as safety net; run full suite.
- [Test coupling to raw SQL] → migrate tests to query counter where needed.
- [Soft-delete field mismatch] → document `borrado_en` convention.

## Migration Plan

No Alembic migration. Code-only change. Rollback by reverting commit.

## Open Questions

- Whether to migrate all of `usuarios` service or keep hybrid (recommended: hybrid, data-access only).
- `SoftDeleteRepository` location: `app/core/repository.py` (chosen) vs per-module.

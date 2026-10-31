# Proposal

## Why

El acceso a datos del proyecto está disperso en funciones libres dentro de `app/modules/usuarios/repository.py`, que mezclan fábricas de sesión (dependencias FastAPI) con operaciones de persistencia. No existe una abstracción compartida de repositorio, por lo que cada módulo duplica consultas, el riesgo de N+1 crece (relaciones con `lazy="raise"`), y la lógica de borrado lógico (`borrado_en IS NULL`) se reimplementa ad hoc. Esta change introduce la jerarquía genérica `BaseRepository[T]` / `SoftDeleteRepository[T]` y la aplica al módulo de identidad/auditoría sin tocar contratos HTTP.

## What Changes

- **New capability `repositorios`**: abstracción genérica de repositorios en `app/core/repository.py`.
- `BaseRepository[T]` con `get_by_id`, `get_all`, `count`, `add`, `update`, `delete`; `add`/`update` ejecutan `flush()` y **nunca** `commit()`.
- `SoftDeleteRepository[T]`: filtra `borrado_en IS NULL` por defecto, agrega `get_by_id_including_deleted` y `soft_delete()`.
- Precarga explícita con `selectinload` en todo método que devuelva agregados (sin N+1, sin lazy loading).
- Repositorios piloto: `UsuarioRepository`, `AsignacionRolRepository`, `IntentoAccesoRepository`, `EventoSeguridadRepository`; constructor tipado sobre `AsyncSession`.
- Refactor de `app/modules/usuarios` (C-09/C-12) para consumir los repositorios **sin cambiar contratos HTTP ni códigos de respuesta**.
- Sin migración Alembic (no cambia esquema).

## Capabilities

### New Capabilities
- `repositorios`: jerarquía genérica de repositorios + repositorios concretos de identidad/auditoría + precarga explícita + soft delete.

### Modified Capabilities
- (ninguna a nivel de requisitos; el refactor preserva contratos HTTP y códigos de respuesta)

## Impact

- Código afectado: `app/core/repository.py` (nuevo), `app/modules/usuarios/repository.py` (refactor), `app/modules/usuarios/service.py` (consumo de repos), tests en `tests/`.
- Sin cambios de API ni de esquema. Sin nuevas dependencias.
- Dependencias: C-07 (domain-models), C-09 (auth-login-jwt). Governance: CRÍTICO.

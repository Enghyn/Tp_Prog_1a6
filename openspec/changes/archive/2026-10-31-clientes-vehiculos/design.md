# Design

## Context

Ver `proposal.md` - Why. El módulo `app/modules/clientes/` ya contiene `models.py` y `repository.py` (`es_duenio_de_vehiculo`); las tablas e índices existen desde C-01. C-10 y C-14 archivados.

## Goals / Non-Goals

**Goals:**
- Módulo clientes completo siguiendo la estructura de `app/modules/usuarios/`.
- 5 endpoints con RBAC, UoW y soft delete.
- Guardas RN-16 (órdenes abiertas) y RN-17 (propiedad).

**Non-Goals:**
- Migraciones Alembic (no hay cambios de schema).
- Concurrencia avanzada ni colas (fuera de alcance caps. 7/8).
- C-17 (registro atómico) y C-18 (órdenes) no se tocan aquí.

## Decisions

1. **Estructura de módulo**: se espeja `app/modules/usuarios/` (schemas, repository, unit_of_work, service, router). Decisión: mantener coherencia con el patrón establecido.
2. **VehiculoRepository extiende SoftDeleteRepository**: soft delete vía `borrado_en`; consultas filtran `borrado_en IS NULL`. ClienteRepository hereda BaseRepository (sin soft delete en cliente).
3. **Detección de órdenes abiertas**: query `EXISTS` sobre `orden_trabajo JOIN estado_orden WHERE vehiculo_id = ? AND es_final = false`. Se ejecuta en el service antes de `delete()`. Alternativa considerada: trigger DB; descartada porque la regla es de negocio y se valida en service con 409 explícito.
4. **Resolución de cliente para `/mis-vehiculos`**: buscar `Cliente` por `usuario_id` (índice único `uq_cliente_usuario`); si no existe → 404. Los vehículos se obtienen por `cliente_id`.
5. **Ownership**: reutilizar `es_duenio_de_vehiculo` (C-10) para endpoints sobre vehículo ajeno; `/mis-vehiculos` usa el cliente del usuario autenticado.
6. **RBAC**: `POST /clientes`, `GET /clientes/{id}`, `POST /clientes/{id}/vehiculos`, `DELETE /vehiculos/{id}` con `require_roles("RECEPCION","ADMIN")`; `GET /mis-vehiculos` con `require_roles("CLIENTE")`.
7. **UoW**: cada mutación dentro de `async with uow:`; repositorios hacen `flush()`, commit en `__aexit__`.
8. **Errores**: subclases de `AppError` (`ConflictoError`, `NoEncontradoError`, `ProhibidoError`) → 409/404/403 con body `{"detail","codigo"}`.
9. **Selectinload**: `GET /clientes/{id}` precarga vehículos con `selectinload(Cliente.vehiculos)`.
10. **Mount**: router de clientes en `router_protegido` en `main.py`.

## Risks / Trade-offs

- [Race en soft delete] → mitigación: índice único parcial vigente; check de órdenes abiertas + delete en misma transacción.
- [Open-order check ordering] → verificar órdenes antes de marcar borrado; si falla, rollback.
- [Cliente sin usuario asociado] → `/mis-vehiculos` devuelve 404 si no hay cliente para el usuario.

## Migration Plan

Sin migración Alembic. Verificar `alembic check` limpio. Rollback: revertir código; no hay cambios de datos.

## Open Questions

- (ninguna)
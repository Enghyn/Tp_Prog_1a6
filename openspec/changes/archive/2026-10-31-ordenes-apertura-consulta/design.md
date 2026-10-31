# Design

## Context

El módulo `app/modules/ordenes/` ya define los modelos `EstadoOrden`, `OrdenTrabajo`, `ItemOrden` e `HistorialEstadoOrden` con sus CHECKs, UNIQUE e índices. No hay repositorios, servicio ni router. El esquema de base de datos, los triggers RN-15 y el seed de `estado_orden` ya están en la migración inicial y en `seed.py`. Se sigue el patrón de los módulos `clientes` (C-15) y `repuestos` (C-16). Ver `proposal.md` para la motivación.

## Goals / Non-Goals

**Goals:**
- Apertura atómica de órdenes con precios copiados del catálogo y total calculado en servidor.
- Consultas con precarga explícita (`selectinload`) de `vehiculo`, `items.repuesto` y `mecanico`, sin N+1.
- Autorización por propiedad para `GET /ordenes/{id}` (RECEPCION/ADMIN, mecánico asignado o dueño del vehículo).
- Catálogo de estados de solo lectura y ordenado por `posicion`.

**Non-Goals:**
- Transiciones de estado (inicio, terminación, cancelación) → C-19.
- Consumo de stock y movimientos → C-19.
- Notificaciones al cliente → C-20.
- Concurrencia avanzada / bloqueos → fuera de alcance (cap. 7).

## Decisions

1. **Estructura de módulo**: espejo de `repuestos`: `repository.py`, `unit_of_work.py`, `schemas.py`, `service.py`, `router.py`. El `repository.py` existente se amplía (hoy solo contiene `es_duenio_de_orden`); se agregan `OrdenRepository`, `ItemOrdenRepository`, `EstadoOrdenRepository` y `HistorialEstadoOrdenRepository`. `OrdenesUnitOfWork` expone `ordenes`, `items`, `estados`, `historial`.

2. **Repositorios**:
   - `OrdenRepository(BaseRepository[OrdenTrabajo])`: `get_by_id` con `selectinload(OrdenTrabajo.vehiculo)`, `selectinload(OrdenTrabajo.items).selectinload(ItemOrden.repuesto)` y `selectinload(OrdenTrabajo.mecanico)`; `get_all` con los mismos loads y filtros (`estado`, paginación).
   - `ItemOrdenRepository(BaseRepository[ItemOrden])`: persistencia de líneas; no valida unicidad en código, se apoya en `uq_item_orden_repuesto` (IntegrityError → 409).
   - `EstadoOrdenRepository(BaseRepository[EstadoOrden])`: solo lectura; `update`/`delete` lanzan `NotImplementedError` (append-only del catálogo, análogo a RN-11).
   - `HistorialEstadoOrdenRepository(BaseRepository[HistorialEstadoOrden])`: solo `add`; `update`/`delete` lanzan `NotImplementedError` (RN-15, trigger de BD).
   - `es_duenio_de_orden` (existente) se conserva tal cual para la fachada `app.core.dependencies.es_duenio_de_orden`.

3. **Relación ORM `ItemOrden.repuesto`**: el modelo actual no la declara. Se agrega una relación unidireccional `repuesto: Optional[Repuesto]` en `ItemOrden` (sin `back_populates`, `lazy="raise"`) para permitir `selectinload(ItemOrden.repuesto)`. Es solo cambio de ORM, sin migración.

4. **UoW**: `OrdenesUnitOfWork(UnitOfWork)` compone los cuatro repositorios con inicialización perezosa, igual que `ClientesUnitOfWork`/`RepuestosUnitOfWork`.

5. **Schemas**:
   - `ItemOrdenCreate`: `repuesto_id: int`, `cantidad: int = Field(gt=0)`; `extra="forbid"`.
   - `OrdenCreate`: `vehiculo_id: int`, `falla: str`, `items: list[ItemOrdenCreate] = Field(min_length=1)`; `extra="forbid"`. No incluye `precio_unitario` ni `total`.
   - `ItemOrdenRead`: `id`, `repuesto_id`, `cantidad`, `precio_unitario`, `repuesto: RepuestoRead` (anidado).
   - `OrdenRead`: `id`, `vehiculo_id`, `mecanico_id`, `estado`, `falla`, `creada_en`, `total`, `vehiculo: VehiculoRead`, `items: list[ItemOrdenRead]`, `mecanico: UsuarioRead | None`.
   - `EstadoOrdenRead`: `codigo`, `descripcion`, `posicion`, `es_final`.

6. **Autorización de `GET /ordenes/{id}`**: permitir si el usuario es RECEPCION o ADMIN (roles vigentes), o es el mecánico asignado (`mecanico_id == usuario_id`), o es dueño del vehículo (`es_duenio_de_orden`). Si no cumple ninguna → `ProhibidoError` (403). Si la orden no existe → `NoEncontradoError` (404). El orden de validación es: existencia primero (404), luego permiso (403), para no filtrar existencia a no autorizados? Decisión: verificar existencia primero y luego permiso; un id inexistente siempre 404 aunque el usuario no tenga permiso. Esto coincide con el spec ("inexistente → 404", "sin permiso → 403") y con los tests esperados.

7. **Apertura (`crear_orden`)**:
   1. Verificar que el catálogo `estado_orden` no esté vacío (`estados.count() == 0` → `ConflictoError` 409, RN-19).
   2. Validar que el vehículo exista (reusar `VehiculoRepository` o consulta directa) → 404 si no.
   3. Validar cada repuesto: existe y vigente → 404 si inexistente, 409 si dado de baja (RN-16). Copiar `precio_unitario = repuesto.precio`.
   4. Calcular `total = sum(cantidad * precio_unitario)`.
   5. Rechazar ítems repetidos en el servicio (además de la constraint de BD) → `ReglaNegocioError` 422 (RN-10).
   6. Crear `OrdenTrabajo(vehiculo_id, mecanico_id=None, estado='PENDIENTE', falla, creada_en=now, total)`.
   7. Crear `ItemOrden` por cada ítem.
   8. Crear `HistorialEstadoOrden(orden_id, desde_estado=None, hasta_estado='PENDIENTE', usuario_id, cuando=now)`.
   9. Todo en el mismo UoW; commit al salir del handler.
   - La validación de repuestos vigentes se hace contra `RepuestosUnitOfWork`? Para mantener una sola transacción, se consulta `Repuesto` directamente desde la sesión del `OrdenesUnitOfWork` (mismo `AsyncSession`), reutilizando el modelo `Repuesto` y filtrando `borrado_en IS NULL`. No se abre un segundo UoW.
   - El estado inicial 'PENDIENTE' se obtiene del catálogo (debe existir; el seed lo garantiza). Si no existe 'PENDIENTE' → 409 (subcaso de catálogo vacío / RN-19).

8. **Listado y paginación**: `GET /ordenes` filtra por `estado` opcional (validado contra el catálogo → 422 si inválido), paginación `page`/`size` con `Page`. `GET /mis-ordenes` resuelve el `Cliente` del usuario y filtra órdenes cuyo `vehiculo.cliente_id` coincide; si no hay cliente vinculado → `NoEncontradoError` 404.

9. **`GET /estados-orden`**: consulta `EstadoOrden` ordenado por `posicion` ascendente, sin paginación.

10. **RBAC por endpoint**:
    - `POST /ordenes`: `require_roles("RECEPCION", "ADMIN")`.
    - `GET /ordenes`: `require_roles("RECEPCION", "MECANICO", "ADMIN")`.
    - `GET /ordenes/{id}`: autenticado (cualquier rol); la autorización fina se resuelve en el servicio.
    - `GET /mis-ordenes`: `require_roles("CLIENTE")`.
    - `GET /estados-orden`: autenticado (cualquier rol).

11. **Montaje**: en `main.py`, `from app.modules import ordenes as ordenes_router` e `router_protegido.include_router(ordenes_router.router_autenticado)` (el router expone `router_autenticado` y `router_publico` vacío, igual que clientes/repuestos).

12. **Manejo de errores**: `IntegrityError` por `uq_item_orden_repuesto` se traduce a 409 por el handler global; el servicio valida antes para dar 422.

## Risks / Trade-offs

- [N+1 en listado] → `selectinload` encadenado en `OrdenRepository.get_all`; verificar con tests de conteo de queries si es necesario (fuera del alcance de C-18).
- [Relación `ItemOrden.repuesto` agregada sin migración] → solo ORM; si se olvida, `selectinload` falla en runtime. Mitigación: tarea de verificación de import y test de detalle.
- [Vehículo inexistente al abrir] → 404; no se valida `borrado_en` del vehículo porque el historial debe conservar propiedad (análogo a `es_duenio_de_orden`).
- [Estado inicial 'PENDIENTE' ausente] → 409 (RN-19); el seed lo garantiza en entornos normales.
- [Catálogo vacío detectado por `count()`] → consulta adicional por apertura; aceptable.

## Migration Plan

No hay migración. Desplegar código, agregar la relación ORM en `models.py` y montar el router en `router_protegido`. Rollback: revertir el commit de código.

## Open Questions

- Ninguna bloqueante. Los nombres de códigos de error siguen el patrón de `clientes`/`repuestos`.

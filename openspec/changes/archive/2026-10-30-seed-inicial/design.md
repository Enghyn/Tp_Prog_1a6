# Design

## Context

Ver `proposal.md` — Why. El estado actual relevante:

- Existen los modelos de auth (C-06) y de dominio (C-07), con sus migraciones `001_auth_core`, `002_dominio_taller` y `003_solo_agregado`. No hay `seed.py` ni datos iniciales.
- `app/core/seguridad.py` ya expone `hash_password_sync()` para uso exclusivo de scripts/CLI (C-03).
- `test/` mezcla `conftest.py`, `__init__.py`, diez `test_*.py`, `salud.http` y `solo_agregado.sql`. No hay `pytest.ini`.
- `CHANGES.md` define C-08 con governance MEDIO y dependencias C-03 + C-07, ambas completadas.
- La KB §02 declara `seed.py` en la raíz y `test/` con `.http` + `solo_agregado.sql`; esa estructura debe actualizarse para reflejar la nueva convención.

## Goals / Non-Goals

**Goals:**

- Un único cargador canónico (`seed.py`) idempotente, transaccional y seguro para desarrollo.
- Un espejo SQL (`test/seed.sql`) idempotente para carga manual, siendo el único `.sql` de `test/`.
- Datos demo coherentes con RN-14, RN-15 y RN-19, incluido stock y totales calculados.
- Suite pytest movida a `tests/` sin pérdida de cobertura ni de Strict TDD.
- Documentación y roadmap sincronizados con la nueva estructura.

**Non-Goals:**

- Endpoints, servicios, repositorios o Unit of Work (llegan en C-13/C-14 y posteriores).
- Migraciones nuevas o cambios de esquema.
- Datos de producción, anonimización o carga incremental desde archivos externos.
- Suite E2E completa y `.http` por módulo (C-20).

## Decisions

### 1. `seed.py` como script async independiente

- Usa `create_async_engine(configuracion.database_url)` y `async_sessionmaker(expire_on_commit=False)`, con una única transacción (`async with session.begin()`), commit al final y rollback automático ante excepción.
- **Por qué no reutilizar el UoW**: C-14 aún no existe. El seed es un script de carga, no un handler; se documenta como excepción explícita a la regla de commit exclusivo del UoW.
- **Por qué no `create_all`**: prohibido por la regla dura 8; el seed asume `alembic upgrade head` ya ejecutado.
- Los hashes se calculan con `hash_password_sync()` antes de abrir la sesión, fuera de cualquier handler async.
- Salida: logs estructurados por entidad (`creado` / `existente`) y resumen final; códigos de salida `0` éxito, `1` error, `2` aborto por guardia o confirmación faltante.

### 2. Idempotencia por claves naturales + timestamps fijos

No se agregan columnas nuevas. Cada entidad se busca por una clave natural estable:

| Entidad | Clave de búsqueda |
|---|---|
| `estado_orden` | `codigo` |
| `usuario` | `email` |
| `asignacion_rol` | `(usuario_id, rol)` con `revocada_en IS NULL` |
| `cliente` | `documento` |
| `vehiculo` | `(patente)` con `borrado_en IS NULL` |
| `repuesto` | `(codigo)` con `borrado_en IS NULL` |
| `orden_trabajo` | `(vehiculo_id, falla)` con falla marcada `[demo]` |
| `item_orden` | `(orden_id, repuesto_id)` |
| `historial_estado_orden` | `(orden_id, desde_estado, hasta_estado, cuando)` |
| `movimiento_stock` | `(repuesto_id, motivo, cantidad, cuando)` |
| `evento_seguridad` | `(actor, accion)` |

- Los `cuando` y `creada_en` del seed son constantes UTC (enero 2026), no `now()`. Así la re-ejecución encuentra las mismas filas y las tablas de solo-agregado no reciben `UPDATE`/`DELETE` (RN-15).
- Si una entidad ya existe, no se sobrescribe: en particular, no se resetean contraseñas, stock ni precios.
- El catálogo `estado_orden` es la excepción: converge a los valores canónicos mediante `UPDATE` de `descripcion`/`posicion`/`es_final` si difieren (no es tabla de solo-agregado).
- Alternativa descartada: `DELETE` + reinsertar. Los triggers RN-15 bloquean `DELETE` en historial/movimientos y borrar usuarios rompería FKs.

### 3. Datos iniciales concretos

**Usuarios y roles** (contraseñas solo para desarrollo, documentadas en README con advertencia):

| Email | Rol | `debe_cambiar_password` |
|---|---|---|
| `admin@taller.local` | ADMIN | `false` |
| `recepcion@taller.local` | RECEPCION | `false` |
| `mecanico@taller.local` | MECANICO | `true` |
| `cliente@taller.local` | CLIENTE | `false` |

Todas las asignaciones se abren con `desde` fijo, `revocada_en = NULL`, `vence_en = NULL`; `otorgada_por` apunta al admin (el admin queda con `otorgada_por = NULL`).

**Clientes y vehículos:**

| Cliente | Documento | Usuario vinculado | Vehículos |
|---|---|---|---|
| Cliente Demo Uno | `30111222` | `cliente@taller.local` | `AB123CD` Toyota Corolla 2020; `AC456EF` Ford Ranger 2018 |
| Cliente Demo Dos | `30999888` | ninguno | `AD789GH` Volkswagen Gol 2015 |

**Repuestos:**

| Código | Descripción | Precio | Stock final |
|---|---|---|---|
| `FIL-001` | Filtro de aceite | 15000.00 | 10 |
| `ACE-001` | Aceite sintético 5W-30 | 12000.00 | 20 |
| `BAT-001` | Batería 12V 60Ah | 85000.00 | 5 |
| `PAS-001` | Pastillas de freno delanteras | 45000.00 | 8 |

**Órdenes demo:**

| Orden | Vehículo | Estado | Ítems | Total | Historial |
|---|---|---|---|---|---|
| `[demo] Ruido en tren delantero` | `AB123CD` | PENDIENTE | 2 × `PAS-001` | 90000.00 | NULL → PENDIENTE |
| `[demo] Service completo` | `AC456EF` | EN_REPARACION | 1 × `FIL-001` + 2 × `ACE-001` | 39000.00 | NULL → PENDIENTE → EN_REPARACION |
| `[demo] Batería agotada` | `AD789GH` | TERMINADA | 1 × `BAT-001` | 85000.00 | NULL → PENDIENTE → EN_REPARACION → TERMINADA |

- `mecanico_id` se asigna en las órdenes EN_REPARACION y TERMINADA.
- El total se calcula en código como `sum(cantidad × precio_unitario)` con `Decimal`; no se hardcodea.
- Cada repuesto recibe un `movimiento_stock` `ALTA` con cantidad = stock final + consumo de la orden TERMINADA. Para `BAT-001`: ALTA 6 y `TERMINACION` −1, dejando stock 5. El resto: ALTA igual al stock final.
- El movimiento de terminación usa `orden_id` de la orden demo y `usuario_id` del mecánico.
- Se registra un único `evento_seguridad` `SISTEMA` / `seed_inicial`.

### 4. `--reset` destructive vía Alembic

- `python seed.py --reset --si` ejecuta `alembic downgrade base` y `alembic upgrade head` mediante la API de Alembic (`alembic.command` + `alembic.config.Config`), **antes** de crear el event loop del seed. Así se evita mezclar dos loops async y se respeta RN-15 (las tablas se dropean, no se borran filas).
- Sin `--si` aborta con código 2 y explica la confirmación requerida.
- Si `configuracion.entorno.lower() == "produccion"` y no se pasó `--forzar`, aborta antes de cualquier escritura (también para `--reset`).
- Alternativa descartada: borrar filas en orden inverso de FKs. Imposible en las tres tablas de solo-agregado por los triggers de C-07.

### 5. `test/seed.sql` como espejo manual

- SQL plano con `BEGIN`/`COMMIT`, `INSERT ... ON CONFLICT DO NOTHING` para entidades con clave única y `INSERT ... SELECT ... WHERE NOT EXISTS` para movimientos e historial.
- Los ids se resuelven con subconsultas por clave natural (`email`, `codigo`, `documento`, `patente`, `falla`).
- Los hashes bcrypt se congelan en el archivo (precalculados una vez para las contraseñas documentadas). Es la única forma de replicar `hash_password_sync` sin Python; se marcan como credenciales de desarrollo.
- No ejecuta `UPDATE`/`DELETE`, por lo que convive con los triggers RN-15.
- `test/solo_agregado.sql` se mueve a `scripts/verificar_solo_agregado.sql`; así `test/` queda con `.http` + `seed.sql` y se conserva la verificación de triggers.

### 6. Reubicación de la suite pytest

- Se mueven `test/conftest.py`, `test/__init__.py` y los diez `test_*.py` a `tests/`, conservando nombres y contenido. `test_paginacion.py` y `test_pagination.py` se mantienen ambos: prueban la API en español y la compatibilidad en inglés, respectivamente.
- Se agrega `pytest.ini`:
  ```ini
  [pytest]
  testpaths = tests
  asyncio_mode = strict
  pythonpath = .
  ```
  `pythonpath = .` mantiene los imports `from main import app` y `from app...` sin empaquetar el proyecto.
- `test/` queda con `salud.http` y `seed.sql`. Los `.http` por módulo se agregan en C-20.
- Alternativa descartada: dejar la suite en `test/` y solo excluirla con `norecursedirs`; incumple el requisito de que no haya `.py` en `test/`.

### 7. Tests del seed con TDD estricto

- Nuevo `tests/test_seed.py` contra PostgreSQL real (regla dura 9). No se mockea la base.
- Casos: doble ejecución sin cambios en conteos; catálogo canónico; un rol abierto por usuario; al menos un `debe_cambiar_password`; stock = suma de movimientos; totales = suma de ítems; historial sin saltos; evento `SISTEMA` único; `test/seed.sql` dos veces sin duplicar; paridad de conteos entre `seed.py` y el espejo SQL.
- Cada test se escribe primero (RED) y luego se implementa lo mínimo para pasarlo (GREEN), triangulando con una segunda entrada (por ejemplo, segunda ejecución y base vacía).

## Risks / Trade-offs

- **Duplicados en tablas sin clave única** (órdenes, historial, movimientos) → claves naturales estables + timestamps fijos y tests de doble ejecución.
- **Drift entre `seed.py` y `test/seed.sql`** → test de paridad de conteos y claves; el SQL se documenta como espejo, no como fuente de verdad.
- **`--reset` destructivo** → doble guardia (`--si` + `entorno`/`--forzar`), mensajes explícitos y código de salida 2.
- **Hashes bcrypt congelados en SQL** → solo credenciales de desarrollo; README advierte regenerarlos si cambia la política de contraseñas.
- **Mover tests rompe imports o fixtures** → ejecutar la suite completa como red de seguridad antes y después del movimiento; `pytest.ini` con `pythonpath = .`.
- **Datos demo que violan RN-14/RN-15** → el seed solo inserta; nunca actualiza stock ni modifica historial. El invariante stock = suma de movimientos se testea.
- **Seed ejecutado por error en producción** → guardia por `entorno` y advertencia en README/`--help`.

## Migration Plan

1. Ejecutar la suite actual como línea base (`pytest`, hoy sobre `test/`).
2. Mover la suite a `tests/`, agregar `pytest.ini` y verificar que la misma suite pasa.
3. Mover `solo_agregado.sql` a `scripts/` y actualizar referencias.
4. Implementar `seed.py` por incrementos TDD: catálogo → usuarios/roles → repuestos/stock → clientes/vehículos/órdenes → auditoría → reset.
5. Crear `test/seed.sql` y testear doble carga.
6. Actualizar README, KB 02, AGENTS/CLAUDE, CHANGES.md.
7. Rollback: `python seed.py --reset --si` (solo desarrollo) o `alembic downgrade base` + `upgrade head`. No hay migraciones nuevas que revertir.

## Open Questions

Ninguna. Las decisiones de credenciales, datos demo, formato del reset y ubicación de tests quedan cerradas en este diseño.

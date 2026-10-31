# Design

## Context

Ver `proposal.md` para la motivación. El estado actual, verificado en esta máquina:

- PostgreSQL 17.11 en `127.0.0.1:5433`, base `taller_mecanico`, `SHOW TimeZone` → `America/Buenos_Aires`.
- `python -m alembic check` falla con 12 `modify_type` de `TIMESTAMP()` a `DateTime(timezone=True)` (y `UTCDateTime()` para `evento_seguridad.cuando`), más `remove_constraint usuario_email_key` / `add_index ix_usuario_email`.
- `information_schema.columns` confirma 12 columnas `timestamp without time zone`: `asignacion_rol.desde/vence_en/revocada_en`, `evento_seguridad.cuando`, `historial_estado_orden.cuando`, `historial_precio_repuesto.cuando`, `intento_acceso.cuando`, `movimiento_stock.cuando`, `orden_trabajo.creada_en`, `repuesto.borrado_en`, `usuario.password_cambiada_en`, `vehiculo.borrado_en`.
- Las 13 tablas de la base tienen 0 filas (verificado con `count(*)`).
- Revisiones aplicadas: `001_auth_core`, `002_dominio_taller`, `003_solo_agregado` (esta última sólo triggers de solo-agregado).

Restricciones del proyecto relevantes: regla dura #8 (migraciones revisadas, sin `create_all`), #9 (tests contra PostgreSQL real), #3 (`lazy="raise"`), #13 (type hints, `snake_case`). El change es out-of-band y **debe archivarse antes de C-11 `password-lifecycle`**, que persistirá `password_cambiada_en` y reutilizará la comparación RN-07 de C-09.

## Goals / Non-Goals

**Goals:**

- Que modelo, migraciones y base de desarrollo describan el mismo esquema, con `alembic check` limpio.
- Que todo valor temporal leído de la base conserve su instante absoluto y sea timezone-aware.
- Que RN-07 quede cubierta por un test de integración que falle con el esquema naive y pase con el corregido.
- Dejar una guarda de metadata que impida reintroducir columnas `DateTime` naive.

**Non-Goals:**

- Implementar C-11 (`POST /auth/cambiar-password`) ni cambiar el contrato de `autenticacion-sesion`.
- Migrar datos existentes: no hay filas en desarrollo y este change no soporta entornos con datos.
- Crear la revisión `004` o alterar `001`/`002`/`003`.
- Cambiar endpoints, DTOs, cookies o RBAC.

## Decisions

### D1: Corregir modelos y reconstruir el esquema de desarrollo (Opción A), sin nueva revisión

**Decisión**: corregir las inconsistencias del modelo, luego `alembic downgrade base` + `alembic upgrade head` sobre una base vacía. No se crea `004`.

**Rationale**: las revisiones `001` y `002` ya declaran `DateTime(timezone=True)` y, en una instalación nueva, producen el esquema correcto. El desvío existe **sólo** en esta base de desarrollo porque se creó con una versión anterior de las revisiones. Con 0 filas, reconstruir es la vía más simple y deja el esquema idéntico al que obtendría cualquier instalación nueva. Además, una revisión que "arregle" tipos ya creados correctamente sería deuda permanente y contradiría el objetivo de paridad.

**Alternativa descartada (Opción B): nueva revisión `004` con `ALTER COLUMN ... TYPE timestamptz`.** Se descarta porque:
- No hay datos que migrar; el `ALTER` no aporta valor y agrega riesgo (conversión implícita según `TimeZone` de sesión si algún día hubiera filas).
- Enmascara la causa real (revisiones editadas tras aplicarse) en lugar de corregirla y documentarla.
- Dejaría `001`/`002` y la realidad de la base reconciliadas sólo por un parche posterior, complicando futuros `alembic check` en entornos nuevos.
- La regla correcta es: las revisiones aplicadas son inmutables; los cambios futuros de esquema van en revisiones nuevas.

### D2: `EventoSeguridad.cuando` con `sa_type` explícito

**Decisión**: `cuando: datetime = Field(nullable=False, sa_type=DateTime(timezone=True), sa_column_kwargs={"server_default": func.now()})`.

**Rationale**: sin `sa_type`, SQLModel infiere `UTCDateTime`, un `TypeDecorator` cuyo `impl` es `DateTime(timezone=True)`. Aunque el `impl` es correcto, Alembic compara el tipo decorado contra `DateTime(timezone=True)` de la migración y reporta drift incluso en una base nueva. Declarar el tipo explícito alinea metadata, migración y DDL, y conserva `server_default=func.now()`.

**Alternativa descartada**: usar `UTCDateTime` también en la migración. Requeriría editar `001`, ya aplicada, y acoplaría el DDL a un detalle de SQLModel.

### D3: `Usuario.email` como `UniqueConstraint`, no como índice único

**Decisión**: `email: str = Field(unique=True, nullable=False)` (se elimina `index=True`).

**Rationale**: la migración `001` declara `sa.UniqueConstraint("email")`, que PostgreSQL materializa como constraint `usuario_email_key` **y** como índice btree único implícito. El modelo actual declara `index=True, unique=True`, que SQLModel traduce a un `Index` único llamado `ix_usuario_email`: funcionalmente equivalente (ambos garantizan unicidad y ambos son indexados), pero estructuralmente distinto para Alembic. Alinear el modelo con la migración evita editar una revisión ya aplicada y elimina el drift sin perder rendimiento.

**Alternativa descartada**: reescribir `001` para emitir `Index("ix_usuario_email", unique=True)`. Prohibido: la revisión ya está aplicada y es inmutable; además obligaría a reconstruir cualquier entorno existente por un detalle cosmético.

### D4: Regla de proceso — revisiones aplicadas inmutables

**Decisión**: dejar registrado en el change que una revisión de Alembic ya aplicada **nunca** se edita. Cualquier cambio de esquema posterior se expresa en una revisión nueva (`004+`) con su `downgrade` correspondiente. La corrección de esta incidencia se limita a modelos + reconstrucción de una base vacía; no sienta precedente para editar revisiones.

**Rationale**: la causa raíz es exactamente esa edición. Sin la regla, el problema reaparece. La verificación repetible es `python -m alembic check` limpio; se recomienda incorporarlo a CI cuando exista pipeline (fuera del alcance de este change).

### D5: Auditoría de campos temporales y guarda de metadata

**Decisión**: recorrer `SQLModel.metadata.tables` en un test y exigir que toda columna `DateTime` (incluyendo `TypeDecorator` cuyo `impl` sea `DateTime`) tenga `timezone is True`. El test falla listando tabla/columna infractoras.

**Rationale**: la auditoría manual de hoy no impide que un cambio futuro introduzca un `datetime` naive. La guarda convierte la regla en un fallo de test. Se ejecuta sin base de datos, por lo que protege incluso en entornos sin PostgreSQL.

### D6: Tests de integración reales con zona horaria no-UTC forzada

**Decisión**: agregar tests contra PostgreSQL real (sin mocks) que ejecutan `SET TIME ZONE 'America/Buenos_Aires'` en la misma conexión de la sesión bajo prueba antes de insertar/leer. Comparar instantes con `.astimezone(timezone.utc)` y precisión de microsegundos.

**Rationale**: el fixture `test_db_session`/`contexto_auth` ya usa PostgreSQL real con rollback. En un servidor CI con `TimeZone=UTC`, el bug no se reproduce (escribir 01:00 UTC en una columna naive guarda 01:00 y se relee 01:00 naive, sin corrimiento); forzar una zona no-UTC hace el test determinista en cualquier entorno. `America/Buenos_Aires` tiene offset -03:00, suficiente para que el corrimiento sea evidente y coincida con la base de desarrollo.

**Alternativa descartada**: mockear la sesión o comparar sólo tipos. No habría detectado el agujero RN-07, que depende del round-trip real por PostgreSQL.

### D7: Verificación E2E de RN-07 sobre datos persistidos

**Decisión**: test que inserta un `Usuario` con `password_cambiada_en` UTC aware, fuerza `TimeZone` no-UTC, emite un token con `iat` 10 minutos antes y llama `GET /auth/yo` con la cookie; espera `401`. Luego repite con `iat` posterior y espera `200`.

**Rationale**: el test actual (`tests/test_auth_sesion.py:236`) construye un `Usuario` en memoria y mockea `sesion.get`, por lo que nunca pasa por la columna. Con el esquema naive, el valor persistido `2026-10-31T01:00:00+00:00` se guarda como `2026-10-30 22:00:00`, se relee naive y `token_anterior_al_cambio` lo etiqueta como UTC: el `iat` de `00:50 UTC` queda **después** de `22:00 UTC` y el token se acepta. El test nuevo espera `401`, por lo que **falla antes del fix** y pasa después. No se modifica el test unitario existente ni el contrato de `autenticacion-sesion`; RN-07 se corrige, no se redefine.

## Risks / Trade-offs

- **Reconstrucción destructiva** → Sólo se ejecuta si un script de preflight confirma 0 filas en **todas** las tablas; si alguna tiene filas, aborta con código distinto de cero y el change se detiene. La base objetivo es local (`127.0.0.1:5433`), de desarrollo. Se documenta un `pg_dump` opcional antes del `downgrade`.
- **Entornos con datos quedarían fuera de cobertura** → Este change no los soporta. Si existiera un entorno con filas, la estrategia correcta sería una revisión `004` separada con `ALTER TYPE ... USING` explícito; se registra como follow-up, no como parte de este change.
- **`downgrade` roto en `001`/`002`/`003`** → La verificación escalonada (`downgrade 002`, `downgrade 001`, `downgrade base`) detecta fallos por FKs, índices o triggers. Corregir un `downgrade` roto está dentro del alcance.
- **Tests pasan por casualidad en CI UTC** → Mitigado con `SET TIME ZONE 'America/Buenos_Aires'` en la conexión del test y comparación por instante UTC.
- **Precisión de microsegundos** → `timestamptz` en PostgreSQL conserva microsegundos; los tests comparan el instante completo, no sólo el segundo.
- **Recurrencia de ediciones a revisiones aplicadas** → Regla D4 documentada y `alembic check` como verificación final; se recomienda sumarlo a CI.
- **Gobernanza** → Nivel **CRÍTICO**: toca seguridad de sesiones (RN-07) y reconstruye esquema. Requiere aprobación humana explícita antes del paso destructivo.

## Migration Plan

Orden de ejecución (detallado en `tasks.md`):

1. **Preflight abortante**: confirmar `alembic current` en `003_solo_agregado`; ejecutar verificación de filas en las 13 tablas; si alguna `count(*) > 0`, abortar. Backup opcional con `pg_dump`.
2. Aplicar las correcciones de modelo (`EventoSeguridad.cuando`, `Usuario.email`, auditoría de datetimes).
3. Ejecutar los tests nuevos: la guarda de metadata pasa; los round-trips y RN-07 fallan contra el esquema naive (confirmación TDD).
4. `python -m alembic downgrade base` → verificar que no quedan tablas de dominio (sólo `alembic_version`).
5. `python -m alembic upgrade head` → verificar en `information_schema` que las 12 columnas son `timestamp with time zone`.
6. `python -m alembic check` → sin operaciones nuevas.
7. Verificación de downgrades escalonada: `downgrade 002_dominio_taller`, `downgrade 001_auth_core`, `downgrade base`, y `upgrade head` final.
8. `python -m pytest -v` completo.

**Rollback**: si algo falla tras el `downgrade`, `upgrade head` reconstruye el esquema desde cero (no hay datos que perder). Si el preflight detecta filas, no se destruye nada: se aborta y se re-planifica con una revisión `004`.

## Open Questions

Ninguna. La estrategia (Opción A), el alcance de tests y la prohibición de `004` fueron aprobados explícitamente por el usuario.

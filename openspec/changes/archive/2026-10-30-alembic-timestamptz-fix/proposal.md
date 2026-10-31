# Proposal

## Why

`python -m alembic check` falla contra la PostgreSQL local (17.11, base `taller_mecanico`, `TimeZone=America/Buenos_Aires`): las revisiones `001_auth_core` y `002_dominio_taller` se editaron **después** de aplicarse y hoy declaran `DateTime(timezone=True)`, pero la base se creó cuando declaraban `DateTime()` naive. El esquema vivo tiene 12 columnas `timestamp without time zone`, el modelo `EventoSeguridad.cuando` sigue siendo inconsistente aun en una base nueva, y la unicidad de `usuario.email` está representada de forma estructuralmente distinta entre modelo y migración.

Esto no es sólo ruido de paridad: escribir un instante UTC aware en una columna naive lo guarda como hora de pared local y lo devuelve sin `tzinfo`. `token_anterior_al_cambio()` (RN-07) vuelve a etiquetarlo como UTC, introduciendo un desfase de 3 horas: un token emitido en las 3 horas previas a un cambio de contraseña **no se invalida**, abriendo un agujero de seguridad. El change debe aterrizar antes de C-11 `password-lifecycle`, que persiste `password_cambiada_en` y depende de esta comparación.

## What Changes

- **Corregir inconsistencias de modelo (sin nueva migración)**:
  - `EventoSeguridad.cuando` → `sa_type=DateTime(timezone=True)` conservando `server_default=func.now()`.
  - `Usuario.email` → `Field(unique=True, nullable=False)` (sin `index=True`), alineado con el `UniqueConstraint` que ya emite la migración `001`.
  - Auditar todos los campos `datetime` de `app/modules/*/models.py`; toda columna temporal debe ser timezone-aware.
- **Reconstruir el esquema de desarrollo** con `alembic downgrade base` + `alembic upgrade head`, previa verificación abortante de que **todas** las tablas están vacías. No se crea una revisión `004`.
- **Añadir guardas de regresión**:
  - Test de metadata que falla si cualquier columna `DateTime` del `SQLModel.metadata` no es `timezone=True`.
  - Tests de integración contra PostgreSQL real (sin mocks) que insertan, leen y comparan instantes bajo una sesión con `TimeZone` no-UTC.
  - Test E2E de RN-07 sobre datos persistidos: token anterior a `password_cambiada_en` → `401`; token posterior → `200`.
- **Fijar la regla de proceso**: una revisión de Alembic ya aplicada es inmutable. Todo cambio futuro de esquema entra en una revisión nueva (`004+`).

## Capabilities

### New Capabilities

_(ninguna)_

### Modified Capabilities

- `persistencia-base`: se agregan requisitos de columnas temporales con zona horaria, paridad modelo↔migración (`alembic check` limpio), conservación del instante al releer datos persistidos (soporte de RN-07) y prohibición de columnas `DateTime` naive.

## Impact

- **Modelos**: `app/modules/usuarios/models.py` (`EventoSeguridad`, `Usuario`); auditoría del resto de `app/modules/*/models.py`.
- **Tests**: nuevos `tests/test_temporal_types.py` y `tests/test_auth_rn07_integracion.py`; se conserva `tests/test_auth_sesion.py` (unitario con mocks) sin cambios.
- **Base de datos de desarrollo**: reconstrucción destructiva habilitada únicamente porque las 13 tablas tienen 0 filas (verificado). Producción/CI no se tocan.
- **Migraciones**: `001_auth_core`, `002_dominio_taller` y `003_solo_agregado` no se modifican; se valida que sus `downgrade` funcionen.
- **Contratos**: no cambia ningún endpoint ni el contrato de `autenticacion-sesion`; RN-07 se corrige, no se redefine.
- **Orden**: change out-of-band (no es C-01..C-20); **debe archivarse antes de C-11** `password-lifecycle`.
- **Fuera de alcance**: nuevas funcionalidades, lógica de cambio de contraseña (C-11), migración de datos históricos (no hay filas), cambios de contrato HTTP.

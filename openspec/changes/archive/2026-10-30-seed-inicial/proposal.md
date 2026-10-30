# Proposal

## Why

La base de datos migrada queda vacía: sin el catálogo `estado_orden` no se puede crear ninguna orden (RN-19), y sin usuarios, roles, repuestos ni clientes no hay forma de ejercer los flujos del taller ni los archivos `.http` de integración. Además, `test/` hoy mezcla la suite pytest (`conftest.py`, `test_*.py`) con los artefactos manuales, cuando la convención pedida es que esa carpeta contenga únicamente archivos `.http` y un solo `.sql`.

Este change entrega un estado inicial reproducible para desarrollo y pruebas, y ordena la carpeta de tests sin perder cobertura ni el modo Strict TDD.

## What Changes

- **Nuevo `seed.py` idempotente** en la raíz del proyecto:
  - Catálogo `estado_orden` canónico: `PENDIENTE` (1), `EN_REPARACION` (2), `TERMINADA` (3, final) y `CANCELADA` (4, final) (RN-19).
  - Usuarios base ADMIN, RECEPCION, MECANICO y CLIENTE con contraseña hasheada mediante `hash_password_sync()`, sus asignaciones de rol abiertas y al menos un usuario con `debe_cambiar_password=True`.
  - Repuestos con stock inicial y su `movimiento_stock` de motivo `ALTA` (RN-14).
  - Clientes, vehículos y tres órdenes demo en estados distintos, con ítems, total calculado en servidor e historial de estados coherente.
  - Un evento de auditoría `evento_seguridad` con `actor='SISTEMA'` y `accion='seed_inicial'`.
  - Re-ejecutable sin duplicar filas; `--reset` destructivo documentado y protegido contra entornos de producción.
- **Nuevo `test/seed.sql`**: espejo SQL idempotente del seed, pensado para carga manual con `psql`. Será el **único** archivo `.sql` dentro de `test/`.
- **BREAKING (solo tooling/desarrollo)**: la suite pytest se muda de `test/` a `tests/` (`conftest.py`, `test_*.py`, `__init__.py`). Se agrega `pytest.ini` con `testpaths = tests`. `test/` queda con archivos `.http` y `seed.sql` únicamente.
- **Movimiento de `test/solo_agregado.sql`** a `scripts/verificar_solo_agregado.sql`, actualizando las referencias de la KB, el README y `CHANGES.md`.
- **Documentación**: README con credenciales de desarrollo, `python seed.py`, `pytest tests/`; KB 02 con la nueva estructura de carpetas; `CHANGES.md` con las referencias de C-07/C-20 ajustadas.

## Capabilities

### New Capabilities

- `seed-inicial`: carga reproducible e idempotente del estado inicial conocido de la base (catálogo, usuarios/roles, repuestos/stock, clientes/vehículos, órdenes demo y auditoría) y contrato de organización de las pruebas del repositorio.

### Modified Capabilities

Ninguna. El comportamiento HTTP y los modelos persistentes no cambian; solo se agrega la carga inicial y se reubican artefactos de prueba.

## Impact

- **Archivos nuevos**: `seed.py`, `test/seed.sql`, `tests/` (suite movida), `pytest.ini`, `scripts/verificar_solo_agregado.sql`.
- **Archivos movidos**: `test/conftest.py`, `test/__init__.py`, `test/test_*.py` → `tests/`; `test/solo_agregado.sql` → `scripts/verificar_solo_agregado.sql`.
- **Documentación**: `README.md`, `knowledge-base/02_descripcion_general.md`, `CHANGES.md`.
- **Base de datos**: solo inserciones idempotentes; no hay migraciones nuevas ni cambios de esquema.
- **API**: sin cambios de endpoints, contratos ni códigos HTTP.
- **Riesgo de seguridad**: el seed crea usuarios con roles y contraseñas conocidas de desarrollo. Se mitiga negándose a ejecutar con `entorno=produccion` salvo `--forzar` explícito y documentando que las credenciales son solo locales.
- **Governance**: MEDIO según `CHANGES.md`, con revisión humana obligatoria de credenciales, roles y del `--reset` destructivo.

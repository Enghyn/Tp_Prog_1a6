# Tasks

## 1. Baseline y preparación

- [x] 1.1 Ejecutar `pytest -q` sobre la suite existente y verificar que está verde (378 passed) antes de tocar nada; registrar el conteo como línea base.
- [x] 1.2 Verificar `alembic check` limpio y head `003_solo_agregado`; documentar en la propuesta si difiere.
- [x] 1.3 Registrar el marker `smoke` en `pytest.ini` (`markers = smoke: pruebas end-to-end del flujo completo`) y verificar que `pytest --co -q` sigue recolectando sin errores.

## 2. Artefactos manuales `.http` por módulo (en `test/`)

- [x] 2.1 Crear `test/usuarios.http` con variables `@baseUrl`, `@adminEmail`, `@adminPassword`, casos felices y errores para `/usuarios`, `/usuarios/{id}/roles`, `/eventos` (201/409/422, 200/404, 200/409, 200/422) y verificar que el archivo abre sin errores de sintaxis en REST Client.
- [x] 2.2 Crear `test/clientes.http` con variables y casos para `/clientes`, `/clientes/{id}`, `/clientes/{id}/vehiculos`, `/vehiculos/{id}`, `/mis-vehiculos` (201/409/422, 200/404, 204/404/409, 200) y verificar captura de cookie `access_token`.
- [x] 2.3 Crear `test/repuestos.http` con variables y casos para `/repuestos` (GET/POST/PATCH/DELETE/reponer/movimientos/precios) con los códigos declarados y verificar casos de stock/precio.
- [x] 2.4 Crear `test/ordenes.http` con variables y casos para `/ordenes`, `/ordenes/{id}`, `/ordenes/{id}/iniciar|terminar|cancelar`, `/estados-orden`, `/mis-ordenes` con los códigos declarados y verificar captura de cookie.
- [x] 2.5 Revisar `test/auth.http` y `test/registro.http` existentes para asegurar que incluyen variables de entorno y cookie `access_token`; ajustar si falta algún caso declarado en `06_funcionalidades.md` y verificar que no se duplican credenciales hardcodeadas.

## 3. Suite pytest de contrato

- [x] 3.1 Crear `tests/test_contrato_endpoints.py` con un test por endpoint de `06_funcionalidades.md` que aserta el código HTTP feliz y al menos un error donde esté declarado; ejecutar `pytest tests/test_contrato_endpoints.py -q` y verificar verde.
- [x] 3.2 Crear `tests/test_cobertura_rn.py` que verifique que cada RN-01..RN-20 tiene al menos un test que la ejerce (referenciando los tests existentes); ejecutar y verificar que no reporta RN faltante.
- [x] 3.3 Si `test_cobertura_rn.py` reporta una RN sin cobertura, agregar el test mínimo faltante en el módulo correspondiente (no en el archivo de cobertura) y verificar que la RN queda cubierta.

## 4. Smoke E2E

- [x] 4.1 Crear `tests/test_smoke_e2e.py` marcado `@pytest.mark.smoke` con el flujo completo: registro → login (captura cookie) → alta cliente/vehículo (admin) → apertura de orden → iniciar (mecánico) → terminar → `/mis-ordenes` y `/repuestos/{id}/movimientos`; ejecutar `pytest -m smoke -q` y verificar verde.
- [x] 4.2 Verificar que el smoke no deja la base en estado inconsistente (email único por ejecución) y que pasa sobre una base recién migrada y sembrada.

## 5. Script operativo `scripts/verificar`

- [x] 5.1 Crear `scripts/verificar` (Python con shebang) que ejecute: lint opcional (`ruff check .` si está instalado), `pytest -q`, `alembic check` y `psql ... -f scripts/verificar_solo_agregado.sql` (si `psql` está disponible); salir con código != 0 ante cualquier fallo.
- [x] 5.2 Crear `scripts/verificar.bat` (wrapper Windows) que invoque `python scripts\verificar` y propagar el código de salida; verificar ejecución en Windows.
- [x] 5.3 Agregar opción `--reset` al script que invoca `python seed.py --reset --si` antes de los tests; verificar que `python scripts/verificar --reset` recrea el esquema y pasa.
- [x] 5.4 Verificar que el script falla (exit != 0) ante un test roto (inyectar un fallo temporal y revertirlo) y ante warning de sesión abierta (correr con `-W error`).

## 6. README final

- [x] 6.1 Actualizar `README.md` con secciones: variables de entorno (tabla), `alembic upgrade head`, `python seed.py` (y `--reset --si`), `pytest` (y `pytest -m smoke`), arranque con uvicorn, ejecución de `scripts/verificar_solo_agregado.sql` y de `scripts/verificar`.
- [x] 6.2 Documentar credenciales de desarrollo y la nota sobre `mecanico@taller.local` con `debe_cambiar_password=true`; verificar que los comandos documentados corren tal cual.

## 7. Verificación RN-15 sobre base real

- [x] 7.1 Migrar y sembrar la base (`alembic upgrade head` + `python seed.py`) y ejecutar `psql "$DATABASE_URL" -f scripts/verificar_solo_agregado.sql`; verificar que reporta OK en los 6 casos (3 tablas × 2 operaciones) y ningún SKIP.
- [x] 7.2 Documentar el resultado (salida del script) en el README o en una nota del change.

## 8. Validación final

- [x] 8.1 Ejecutar `pytest -q` completo sobre base recién migrada y sembrada; verificar 0 fallos y 0 warnings de sesión abierta.
- [x] 8.2 Ejecutar `alembic check` y verificar limpio.
- [x] 8.3 Ejecutar `openspec validate integracion-e2e --strict` y `openspec status --change integracion-e2e --json`; verificar que los artefactos están completos y sin errores.
- [x] 8.4 Marcar `[x]` en `CHANGES.md` para C-20 tras archivar (pendiente hasta archive).

## Workflow follow-up

- Archivar el change tras revisar los requisitos (`/opsx:archive integracion-e2e`) y marcar `[x]` en CHANGES.md.
- Verificar el resultado archivado.
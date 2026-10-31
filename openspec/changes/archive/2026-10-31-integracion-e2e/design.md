# Design

## Context

Ver `proposal.md` (Why/What). El proyecto ya tiene 378 tests verdes, `alembic check` limpio y head `003_solo_agregado`. Los artefactos existentes: `test/salud.http`, `test/auth.http`, `test/registro.http`, `test/seed.sql`, `scripts/verificar_solo_agregado.sql`, `README.md` inicial. `tests/conftest.py` provee fixtures `cliente`, `test_db_session`, `contexto_auth`, `seed_session_factory`. No se toca `app/`: solo tests, docs, scripts y `.http`. Restricción dura #15: `test/` solo `.http`/`.sql`, `tests/` solo pytest.

## Goals / Non-Goals

**Goals:**
- Consolidar la verificación del contrato completo (endpoints + RN-01..RN-20) sobre PostgreSQL real.
- Proveer un smoke E2E reproducible del flujo completo.
- Proveer un script operativo `scripts/verificar` ejecutable en Windows (y portable a POSIX).
- Documentar el flujo final en `README.md`.
- Mantener la separación estricta `test/` (manuales) vs `tests/` (pytest).

**Non-Goals:**
- No se agregan endpoints, migraciones ni cambios de esquema.
- No se introduce CI/CD ni colas (fuera de alcance, cap. 8).
- No se cambia la configuración de pytest (`pytest.ini`) ni se agregan dependencias nuevas.
- No se reescriben tests existentes; solo se referencian/agrupan.

## Decisions

1. **Capacidad nueva `verificacion-contrato`** (en `openspec/specs/verificacion-contrato/`) en lugar de modificar capacidades existentes: el cambio no altera requisitos de ningún módulo, solo agrega el contrato de verificación.

2. **`.http` por módulo en `test/`** usando el formato de la extensión REST Client (VS Code) / JetBrains HTTP Client, que es el estándar de facto para archivos `.http`:
   - Variables de entorno/archivo: `@baseUrl = http://localhost:8000`, `@adminEmail = admin@taller.local`, etc. Las credenciales de desarrollo se toman de `README.md`.
   - Cookie `access_token`: se captura del `Set-Cookie` de `POST /auth/login` con `# @name login` y se reutiliza vía `{{login.response.headers.Set-Cookie}}` (o se pega manualmente). Se documenta en cada archivo.
   - Un archivo por módulo: `salud.http`, `auth.http`, `registro.http` (ya existen), más `usuarios.http`, `clientes.http`, `repuestos.http`, `ordenes.http`.
   - Cada archivo incluye sección "Casos felices" y "Casos de error" con los códigos declarados en `06_funcionalidades.md`.

3. **Suite de contrato**: NO se crea un único archivo monolítico. Se reutilizan los tests existentes (`tests/test_*.py`) que ya cubren endpoints y RNs. Se agrega un único archivo `tests/test_contrato_endpoints.py` que actúa como índice/verificación de cobertura: para cada endpoint de `06_funcionalidades.md` un test mínimo que aserta el código HTTP feliz y (donde aplica) un error. Esto evita duplicar lógica y mantiene TDD. La cobertura RN-01..RN-20 se verifica por un test `tests/test_cobertura_rn.py` que importa/ejecuta (o marca) los tests existentes que ejercen cada regla; si falta cobertura para alguna RN, el test falla con un mensaje nombrando la RN faltante.

   Alternativa considerada: un solo `test_contrato_endpoints.py` gigante. Rechazada por duplicación y mantenimiento.

4. **Smoke E2E**: un solo test `tests/test_smoke_e2e.py` marcado con `@pytest.mark.smoke` (marker registrado en `pytest.ini` mediante `markers = smoke: ...`). Usa la base real vía `contexto_auth` o un flujo que crea sus propios datos dentro de una transacción con rollback. El flujo: registrar cliente nuevo → login (capturar cookie) → (admin) alta cliente/vehículo → apertura de orden → iniciar (mecánico) → terminar → `/mis-ordenes` y `/repuestos/{id}/movimientos`. Se usan credenciales del seed para los roles ADMIN/MECANICO y un email único generado para el registro.

5. **Marker `smoke`**: se agrega a `pytest.ini` la línea `markers = smoke: pruebas end-to-end del flujo completo`. No cambia `testpaths`. El script `scripts/verificar` corre `pytest` (todo) y luego `pytest -m smoke` explícitamente (redundante pero explícito) o simplemente `pytest` que ya incluye smoke. Decisión: `pytest` ejecuta todo (incluye smoke); el script además corre `pytest -m smoke` para reportar el smoke por separado. Para no duplicar tiempo, el script corre `pytest` una sola vez y luego `pytest -m smoke --co` (collect-only) como sanity. Simplificación: el script corre `pytest -q` una sola vez; el smoke está incluido.

   Hmm, el alcance pide "lint + tests + smoke". Decisión final: `scripts/verificar` corre (1) lint si hay herramienta disponible (`ruff`/`flake8` opcional, no bloqueante si no está instalado), (2) `pytest -q` (incluye smoke), (3) `alembic check`. Si cualquiera falla, exit code != 0.

6. **`scripts/verificar` multiplataforma**: se implementa como script Python (`scripts/verificar.py`) invocable con `python scripts/verificar.py`, más un wrapper `scripts/verificar` (sin extensión, shebang) y `scripts/verificar.bat` para Windows. Pero la restricción "script `scripts/verificar`" implica un archivo llamado `verificar`. Decisión: crear `scripts/verificar` (archivo sin extensión con shebang `#!/usr/bin/env python3` y código Python), más `scripts/verificar.bat` que invoque `python scripts\verificar.py`... 

   Refinamiento más simple y robusto: crear `scripts/verificar.py` (implementación) y `scripts/verificar.bat` (wrapper Windows) y `scripts/verificar` (wrapper POSIX). Pero la tarea dice "script `scripts/verificar`". Para satisfacer literalmente y que funcione en Windows, se crea `scripts/verificar` como archivo Python (ejecutable vía `python scripts/verificar` o `python scripts\verificar` en Windows; en POSIX vía shebang). Además se documenta en README el comando exacto: `python scripts/verificar` (Windows) / `./scripts/verificar` (POSIX). Esto es ambiguo; se documenta ambos.

   Ambigüedad registrada: en Windows no se puede ejecutar un archivo sin extensión directamente sin asociación; por eso el README prioriza `python scripts/verificar`.

7. **Seeding en CI/verificación**: el script `scripts/verificar` asume una base ya migrada y sembrada (no resetea por defecto, para no destruir datos). Opción `--reset` invoca `python seed.py --reset --si` antes de correr tests. Por defecto no resetea (idempotente). Se documenta.

8. **Warnings de sesión abierta**: se ejecuta pytest con `-W error::pytest.PytestUnraisableExceptionWarning` y `-p no:cacheprovider`? No. Decisión: el script corre `pytest -q -W error` para convertir warnings en errores. Pero eso puede romper por warnings ajenos (deprecations). Alternativa: `-W error::ResourceWarning` y filtro específico para "session is still open"/"unclosed". Decisión pragmática: correr `pytest -q` normal y parsear salida para "warning" de sesión; además correr una segunda pasada `pytest -q -W error::pytest.PytestWarning` solo si no hay ruido. Simplificación final para el script: `pytest -q -W error` y si falla por warnings no relacionados, se documenta la excepción. 

   Mejor: usar filtro de warnings dirigido: `-W error::ResourceWarning` y `-W error::RuntimeWarning` no captura "session open" que es un pytest warning. El warning típico de SQLAlchemy/pytest es `SAWarning` o `pytest.PytestUnraisableExceptionWarning`. Decisión: el script corre `pytest -q` y además `pytest -q -W error::pytest.PytestUnraisableExceptionWarning -W error::ResourceWarning`. Si falla, exit != 0. Se documenta que warnings de sesión abierta son error.

9. **DB seeding en CI**: documentar `TEST_DATABASE_URL` y `DATABASE_URL`. El script no gestiona Docker; asume PostgreSQL disponible (igual que conftest).

10. **`scripts/verificar` lint**: ruff es opcional. Si `ruff` no está instalado, se salta el lint con mensaje "lint skipped (ruff not installed)" y no falla. Si está, corre `ruff check .`. Esto mantiene portabilidad.

## Risks / Trade-offs

- [E2E flakiness por estado compartido] → el smoke usa datos únicos (email con UUID) y transacciones con rollback donde el fixture lo permite; el registro/login real commitea (no rollback) pero con email único evita colisiones. Trade-off: deja datos de prueba en la base; aceptable en dev.
- [Warnings de sesión abierta en tests existentes] → si la suite actual emite alguno, el script falla; se reporta y se corrige en apply (fuera de scope de propose, pero el design lo prevé).
- [`.http` con cookie capture no estándar entre clientes] → se documenta sintaxis REST Client y alternativa manual; no bloqueante porque son artefactos manuales.
- [`scripts/verificar` sin extensión en Windows] → se prioriza `python scripts/verificar`; se provee `.bat` wrapper.
- [RN-15 script requiere filas] → se ejecuta tras seed; si alguna tabla está vacía, reporta SKIP (no éxito). El script `verificar` ejecuta `verificar_solo_agregado.sql` tras seed.

## Migration Plan

Sin migración Alembic. Despliegue: agregar archivos. Rollback: revertir commit. No hay cambios de esquema.

## Open Questions

- Formato exacto de captura de cookie en `.http`: REST Client (`# @name`) vs JetBrains. Se documentan ambos en cada archivo.
- Si el lint (`ruff`) no está en `requirements.txt`: se mantiene opcional; no se agrega dependencia nueva en este change (fuera de alcance). Se puede agregar en un change futuro.
- Si el smoke E2E debe limpiar sus datos: por simplicidad no limpia (email único); documentado como limitación.
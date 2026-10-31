# Proposal

## Why

El proyecto cuenta con 20 changes implementados (378 tests verdes), pero no existe un harness de verificación end-to-end que cierre el contrato completo: no hay `.http` por módulo para `usuarios`, `clientes`, `repuestos` ni `ordenes` (solo `salud`, `auth`, `registro`), no hay una suite pytest que ejerza explícitamente cada regla RN-01..RN-20 ni cada endpoint de `06_funcionalidades.md`, no hay un smoke E2E del flujo completo, no hay un script operativo `scripts/verificar` (lint + tests + smoke) y el `README.md` no documenta el flujo de migración + seed + verificación RN-15. Sin este cierre no se puede demostrar que el contrato HTTP y las reglas de negocio se cumplen sobre una base recién migrada y sembrada, que es la entrega final del TP (capítulo 6).

## What Changes

- Crear `test/*.http` por módulo (`usuarios`, `clientes`, `repuestos`, `ordenes`) además de los existentes (`salud`, `auth`, `registro`), con variables de entorno (`@baseUrl`, `@adminEmail`, etc.), cookie `access_token` y casos felices + errores declarados para cada endpoint de `06_funcionalidades.md`.
- Agregar suite pytest de contrato que verifica que cada endpoint responde el código HTTP esperado y que cada regla RN-01..RN-20 tiene al menos un test que la ejerce (reutilizando los tests existentes y/o añadiendo los faltantes).
- Agregar un smoke E2E (pytest, marcado `smoke`) que recorre el flujo completo: registro → login → alta cliente/vehículo → alta de orden → iniciar → terminar → consulta `/mis-ordenes` y `/repuestos/{id}/movimientos`.
- Agregar `scripts/verificar` (batch/shell) que ejecuta lint + suite completa + smoke sobre base recién migrada y sembrada, y falla ante cualquier warning de sesión abierta.
- Documentar en `README.md` final: variables de entorno, `alembic upgrade head`, `python seed.py`, `pytest`, arranque con uvicorn y ejecución de `scripts/verificar_solo_agregado.sql`.
- Verificar RN-15 sobre base real ejecutando `scripts/verificar_solo_agregado.sql` y confirmando que `UPDATE`/`DELETE` fallan en las tres tablas de solo-agregado.
- Ejecutar `alembic check` final (sin migraciones pendientes).

Sin cambios de esquema, migraciones ni endpoints: solo tests, documentación, scripts y artefactos manuales.

## Capabilities

### New Capabilities
- `verificacion-contrato`: contrato de verificación end-to-end del sistema: cada endpoint de `06_funcionalidades.md` responde el código esperado, cada RN-01..RN-20 tiene al menos un test que la ejerce, el smoke E2E del flujo completo pasa, la verificación RN-15 (script SQL) falla en `UPDATE`/`DELETE` sobre las tres tablas de solo-agregado, la suite completa pasa sobre base recién migrada y sembrada, y no hay warnings de sesión abierta.

### Modified Capabilities
(none)

## Impact
- Código: sin cambios en `app/`. Solo se agregan artefactos de verificación en `test/`, `tests/` y `scripts/`, y se actualiza `README.md`.
- APIs: ninguna nueva ni modificada; se verifica el contrato existente.
- Dependencias: C-11, C-12, C-17 y C-19 archivadas (todas). Reutiliza `tests/conftest.py`, `test/seed.sql` y `scripts/verificar_solo_agregado.sql`.
- Sin migraciones Alembic ni cambios de esquema.
- Governance: MEDIO. Strict TDD aplica a los tests nuevos.
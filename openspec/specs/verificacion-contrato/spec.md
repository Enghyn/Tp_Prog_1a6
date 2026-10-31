# verificacion-contrato Specification

## Purpose
Establece el contrato de verificación end-to-end del sistema Taller Mecánico API: define qué debe comprobarse (endpoints, reglas de negocio, smoke E2E, RN-15, suite completa y ausencia de warnings de sesión) para considerar la entrega final válida.

## Requirements

### Requirement: Cobertura de contrato por endpoint
El sistema SHALL contar con una suite de verificación que ejerce cada endpoint declarado en `06_funcionalidades.md` y valida que responda el código HTTP esperado (feliz y al menos un error por endpoint cuando esté declarado).

#### Scenario: Endpoint responde código esperado
- **WHEN** se invoca un endpoint del contrato con entrada válida y credenciales adecuadas
- **THEN** la respuesta tiene el código HTTP declarado para el caso feliz

#### Scenario: Endpoint responde código de error declarado
- **WHEN** se invoca un endpoint con entrada inválida, sin credenciales o sin permiso suficiente
- **THEN** la respuesta tiene uno de los códigos de error declarados para ese endpoint

### Requirement: Cobertura de reglas de negocio RN-01 a RN-20
El sistema SHALL contar con al menos un test automatizado que ejerce cada regla RN-01 a RN-20, verificando el código HTTP o el efecto observable declarado en `05_reglas_de_negocio.md`.

#### Scenario: Cada regla tiene un test que la ejerce
- **WHEN** se ejecuta la suite de contrato
- **THEN** cada regla RN-01 a RN-20 aparece referenciada por al menos un test que falla si la regla se rompe

### Requirement: Smoke E2E del flujo completo
El sistema SHALL contar con un test de smoke end-to-end que recorra el flujo completo: auto-registro de cliente → login → alta de cliente/vehículo → apertura de orden → inicio → terminación → consulta de `/mis-ordenes` y de `/repuestos/{id}/movimientos`, asertando el estado final y los efectos de stock.

#### Scenario: Flujo completo exitoso
- **WHEN** se ejecuta el smoke E2E sobre una base migrada y sembrada
- **THEN** todas las etapas responden con los códigos esperados y el estado final es consistente (orden TERMINADA, stock descontado, movimiento registrado, orden visible en /mis-ordenes)

### Requirement: Verificación RN-15 sobre base real
El sistema SHALL contar con la ejecución de `scripts/verificar_solo_agregado.sql` sobre una base real con datos, y SHALL fallar si algún `UPDATE` o `DELETE` sobre `historial_estado_orden`, `movimiento_stock` o `historial_precio_repuesto` no es bloqueado por el trigger.

#### Scenario: Triggers bloquean mutaciones
- **WHEN** se ejecuta el script sobre una base con filas en las tres tablas
- **THEN** cada intento de `UPDATE`/`DELETE` falla con el mensaje del trigger y el script reporta OK por cada caso

### Requirement: Suite completa verde sobre base recién migrada y sembrada
El sistema SHALL pasar la suite completa de pytest (`pytest`) sobre una base PostgreSQL recién migrada con `alembic upgrade head` y sembrada con `python seed.py`, sin fallos.

#### Scenario: Suite verde
- **WHEN** se ejecuta `pytest` contra la base recién migrada y sembrada
- **THEN** todos los tests pasan

### Requirement: Ausencia de warnings de sesión abierta
El sistema SHALL no emitir warnings de sesión abierta al finalizar la suite completa; cualquier warning de sesión abierta se considera fallo de la verificación.

#### Scenario: Sin warnings de sesión
- **WHEN** se ejecuta la suite completa con `-W error` (o equivalente)
- **THEN** no se emiten warnings de sesión abierta

### Requirement: Artefactos manuales HTTP por módulo
El sistema SHALL contar con archivos `.http` en `test/` para los módulos `health`, `auth`, `usuarios`, `clientes`, `repuestos` y `ordenes`, con variables de entorno, cookie `access_token` y casos felices + errores declarados.

#### Scenario: Archivos .http presentes y completos
- **WHEN** se inspecciona `test/`
- **THEN** existen `salud.http`, `auth.http`, `registro.http`, `usuarios.http`, `clientes.http`, `repuestos.http` y `ordenes.http` con variables y casos documentados

### Requirement: Script operativo de verificación
El sistema SHALL contar con `scripts/verificar` que ejecute, en orden, lint (si aplica), la suite completa de pytest y el smoke E2E, fallando ante cualquier error o warning de sesión abierta.

#### Scenario: Script falla ante error
- **WHEN** algún test falla
- **THEN** `scripts/verificar` retorna código de salida distinto de cero

### Requirement: Documentación final de ejecución
El sistema SHALL contar con un `README.md` que documente las variables de entorno, `alembic upgrade head`, `python seed.py`, `pytest`, el arranque con uvicorn y la ejecución de `scripts/verificar_solo_agregado.sql`.

#### Scenario: README documenta el flujo
- **WHEN** se lee `README.md`
- **THEN** contiene las secciones de variables de entorno, migración, seed, pruebas, arranque y verificación RN-15

### Requirement: Migraciones al día
El sistema SHALL tener `alembic check` limpio (sin migraciones pendientes) al finalizar la verificación.

#### Scenario: Alembic check limpio
- **WHEN** se ejecuta `alembic check`
- **THEN** reporta que no hay diferencias entre modelos y base

# Tasks

## 1. Persistencia Asíncrona y Ciclo de Vida

- [x] 1.1 Escribir tests unitarios en `test/test_database.py` para validar la creación del motor, la configuración del sessionmaker (`expire_on_commit=False`) y la entrega de sesión sin commit automático
- [x] 1.2 Implementar `app/core/database.py` con `create_async_engine`, `async_sessionmaker` y la dependencia `get_session()` con manejo de contexto asíncrono y verificar que los tests pasen
- [x] 1.3 Conectar la inicialización del motor y el desmantelamiento limpio con `engine.dispose()` en el `lifespan` de `main.py`

## 2. Readiness Probe (`GET /health/ready`)

- [x] 2.1 Escribir tests para el endpoint `GET /health/ready` en `test/test_readiness.py` cubriendo caso exitoso (200) y casos de fallo o timeout de conexión (503)
- [x] 2.2 Implementar el handler `GET /health/ready` en `app/modules/health/router.py` ejecutando `SELECT 1` con timeout acotado y verificar que todos sus tests pasen

## 3. Configuración Asíncrona de Alembic

- [x] 3.1 Configurar `alembic.ini`, `migrations/script.py.mako` y `migrations/env.py` con la plantilla asíncrona conectada a `Settings.database_url`
- [x] 3.2 Ejecutar verificación de configuración de Alembic (`alembic check` o `alembic heads`) confirmando carga correcta de metadatos y entorno asíncrono

## 4. Infraestructura de Testing y Verificación Integral

- [x] 4.1 Configurar fixtures en `test/conftest.py` para conexión a PostgreSQL de pruebas, transacciones con rollback por test y override de la dependencia `get_session`
- [x] 4.2 Ejecutar la suite completa de pruebas (`pytest`) asegurando que tanto los tests preexistentes como los nuevos de base de datos pasen al 100%

# Propuesta

## ¿Por qué?

La API necesita persistencia asíncrona real sobre PostgreSQL sin bloquear el event loop, garantizando un ciclo de vida seguro de conexiones y sesiones por request sin commits automáticos indebidos. Asimismo, se requiere un health check de preparación (`GET /health/ready`) para orquestadores y monitoreo que verifique la conectividad real a la base de datos, y una infraestructura base para migraciones de esquema con Alembic asincrónico.

## ¿Qué cambios?

- **Motor y sesión asíncrona**: Crear `app/core/database.py` con `create_async_engine(settings.database_url, pool_pre_ping=True)` y `async_sessionmaker(expire_on_commit=False)`.
- **Integración con Lifespan**: Guardar engine y sessionmaker en `app.state` durante el arranque de la aplicación y garantizar `await engine.dispose()` al detener la aplicación en `main.py`.
- **Dependencia de sesión**: Implementar `get_session()` como generador asíncrono (`async with`) que entrega una `AsyncSession` por request y garantiza su cierre; bajo ninguna circunstancia realiza `commit()` (responsabilidad exclusiva del Unit of Work).
- **Readiness Probe**: Implementar `GET /health/ready` en `app/modules/health/router.py` que ejecuta `SELECT 1` con timeout acotado, respondiendo 200 si la base está accesible o 503 si la conexión falla o expira.
- **Entorno de migraciones Alembic**: Configurar `alembic.ini` y `migrations/env.py` con la plantilla asincrónica leyendo `Settings.database_url`, junto con `migrations/script.py.mako`.
- **Infraestructura de pruebas con DB real**: Extender `test/conftest.py` con fixtures para PostgreSQL de pruebas, transacciones con rollback por test y override de la dependencia `get_session`.

## Capacidades

### Nuevas Capacidades
- `persistencia-base`: Ciclo de vida del motor de base de datos asíncrono, sesiones por request sin auto-commit, configuración de migraciones Alembic asíncronas y fixtures de prueba con transacciones aisladas.

### Capacidades Modificadas
- `health-check`: Se incorpora el endpoint `GET /health/ready` que valida la disponibilidad y conectividad activa con PostgreSQL con respuesta 200/503.

## Impacto

**Áreas afectadas:**
- `app/core/database.py` (nuevo)
- `app/modules/health/router.py` (modificado con `/health/ready`)
- `main.py` (lifespan inicializa y libera engine y sessionmaker)
- `alembic.ini` y `migrations/` (plantilla asíncrona)
- `test/conftest.py` (fixtures de sesión y transacción para tests)
- `test/test_database.py` / `test/test_readiness.py` (nuevos tests)

**Dependencias:** `C-01`, `C-02`

**Notas:**
- Regla dura: tests contra PostgreSQL real, nunca SQLite.
- Regla dura: `get_session()` nunca hace `commit()`.
- Regla dura: el endpoint `/health/ready` debe manejar timeouts acotados (`asyncio.wait_for`) para no dejar colgadas las solicitudes de verificación.

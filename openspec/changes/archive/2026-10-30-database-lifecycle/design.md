# Diseño Técnico: database-lifecycle

## Contexto

El sistema completó la fase base (C-01 a C-04) con contratos de error uniformes (`AppError`), utilidades criptográficas no bloqueantes (`async-crypto`) y tareas en segundo plano (`background-notifications`). Hasta este punto, la aplicación operaba sin conexión activa a base de datos. Este change introduce la infraestructura asíncrona de persistencia con PostgreSQL, la gestión de sesiones por solicitud y el entorno de migraciones con Alembic.

Para más detalle sobre la motivación, ver `proposal.md`.

## Objetivos y No-Objetivos

**Objetivos:**
- Configurar el motor asíncrono de SQLAlchemy con driver `asyncpg` y el `async_sessionmaker` desacoplado de commits automáticos (`expire_on_commit=False`).
- Integrar la inicialización y el desmantelamiento del pool en el ciclo de vida de la aplicación (`lifespan` en `main.py`).
- Implementar la dependencia FastAPI `get_session()` garantizando el cierre seguro de la conexión por request.
- Implementar el endpoint `GET /health/ready` para monitoreo de disponibilidad de la base de datos con timeout acotado.
- Configurar el entorno de migraciones asíncronas con Alembic (`alembic.ini`, `migrations/env.py`, `migrations/script.py.mako`).
- Diseñar la infraestructura de fixtures para pytest ejecutando transacciones aisladas con rollback contra PostgreSQL real.

**No-Objetivos:**
- No definir modelos de datos de dominio ni tablas de negocio (corresponde a C-06 y C-07).
- No implementar lógica de Unit of Work ni repositorios (corresponde a C-13 y C-14).
- No permitir SQLite bajo ninguna circunstancia (contrato estricto del proyecto).
- No realizar commits en `get_session()` ni en repositorios.

## Decisiones Técnicas

### 1. Motor y SessionMaker (`app/core/database.py`)
- **Decisión**: Utilizar `create_async_engine(settings.database_url, pool_pre_ping=True)` y `async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)`.
- **Razón**: `pool_pre_ping=True` previene errores por conexiones caídas o recicladas por PostgreSQL. `expire_on_commit=False` evita que los atributos de las entidades queden inaccesibles tras un commit en el Unit of Work sin requerir re-queries implícitas.
- **Alternativa descartada**: Sesiones sincrónicas o drivers bloqueantes como `psycopg2`.

### 2. Gestión del Ciclo de Vida en Lifespan
- **Decisión**: Instanciar el engine y el sessionmaker dentro del context manager `lifespan` de FastAPI, registrándolos en `app.state.engine` y `app.state.session_maker`. En el bloque de cierre, ejecutar `await engine.dispose()`.
- **Razón**: Permite la inicialización ordenada al arrancar el servidor y garantiza el drenado y cierre limpio de conexiones sin fugas de sockets al detener Uvicorn.

### 3. Dependencia `get_session()`
- **Decisión**: Proveer una función generadora asíncrona con `async with session_maker() as session: yield session`.
- **Razón**: Asegura que la sesión siempre se cierre al finalizar el request (incluso si ocurre una excepción no capturada). No ejecuta `session.commit()`, delegando la confirmación de transacciones exclusivamente a `UnitOfWork`.

### 4. Readiness Probe (`GET /health/ready`)
- **Decisión**: Ejecutar `await session.execute(text("SELECT 1"))` acotado con `asyncio.wait_for(..., timeout=2.0)`. Si la consulta tiene éxito retorna `200 {"status": "ready"}`; ante `SQLAlchemyError`, error de conexión o `TimeoutError`, retorna `503 Service Unavailable`.
- **Razón**: Un probe de Kubernetes/orquestador no debe quedar colgado si la base de datos se congela o experimenta problemas de red.

### 5. Configuración de Alembic Asincrónico
- **Decisión**: Configurar `migrations/env.py` usando `asyncio.run()` y `connectable.connect()` asíncrono para ejecutar las migraciones en modo online. La URL de la base de datos se toma directamente de `Settings.database_url`.
- **Razón**: Mantiene coherencia con el driver `asyncpg` sin forzar una conexión síncrona secundaria.

### 6. Estrategia de Testing contra PostgreSQL Real
- **Decisión**: Crear un fixture de sesión de pytest que conecta a una base de datos PostgreSQL de prueba (vía `TEST_DATABASE_URL` o fallback a base local de test), iniciando una conexión externa que abre una transacción y hace rollback al finalizar cada test. Sobrescribir `get_session` vía `app.dependency_overrides`.
- **Razón**: Respeta la regla dura #9 (prohibido SQLite, dado que los CHECK constraints, partial unique indexes y triggers son load-bearing en cambios futuros).

### 7. UI Mockups
- **Decisión**: No (no UI). Cambio puramente de infraestructura y persistencia backend.

## Riesgos y Mitigaciones

- **[Riesgo] La base de datos no está disponible durante la ejecución de los tests locales.**  
  → *Mitigación*: Documentar claramente la variable `DATABASE_URL` en `.env.example` y asegurar que los fixtures manejen con mensajes claros la indisponibilidad de PostgreSQL para el entorno de desarrollo.
- **[Riesgo] Bloqueo indefinido en `/health/ready` si PostgreSQL no responde.**  
  → *Mitigación*: Limitar la ejecución de la consulta de verificación con `asyncio.wait_for` a un timeout estricto de 2 segundos.
- **[Riesgo] Conexiones huérfanas al reiniciar el servidor en desarrollo (`--reload`).**  
  → *Mitigación*: Implementación rigurosa de `engine.dispose()` en el cleanup del lifespan.

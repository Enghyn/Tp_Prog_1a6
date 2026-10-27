# Propuesta

## ¿Por qué?

Este cambio establece la estructura base del proyecto API Taller Mecánico. Se configura la estructura del proyecto, las dependencias, la configuración, los endpoints de salud y la infraestructura de pruebas para que todos los cambios posteriores puedan construirse sobre una base consistente y bien estructurada.

## ¿Qué cambios?

- **Estructura del proyecto**: Crear la estructura modular de 6 capas con `app/core/`, `app/modules/{health,usuarios,clientes,repuestos,ordenes}/`, `migrations/` y `test/`
- **Dependencias**: Definir `requirements.txt` con versiones fijadas para FastAPI, SQLModel, SQLAlchemy, asyncpg, Alembic, pydantic-settings, bcrypt, PyJWT, uvicorn, pytest, pytest-asyncio, httpx
- **Configuración**: Implementar `app/core/config.py` con `Configuracion`, añadir `.env.example`, asegurar `.env` en `.gitignore`
- **Inicialización de la aplicación**: Crear `main.py` con `create_app()` y `lifespan` vacío preparado, logging estructurado y router raíz
- **Verificación de salud**: Implementar `GET /health/live` en `app/modules/health/router.py` retornando 200 sin acceder a la base de datos
- **Infraestructura de pruebas**: Añadir `test/conftest.py` y `test/salud.http` con `httpx.AsyncClient`/`ASGITransport`
- **Documentación**: Crear `README.md` con instrucciones de instalación y uso

## Capacidades

### Nuevas Capacidades
- `health-check`: Endpoint básico de verificación de vida sin dependencia de base de datos

### Capacidades Modificadas
<!-- Sin capacidades existentes para modificar -->

## Impacto

**Áreas afectadas:**
- Nueva estructura bajo `app/`, `test/`, `migrations/`
- Nuevos archivos de configuración (`requirements.txt`, `.env.example`, `README.md`, `main.py`)
- Módulos core: `app/core/config.py`, `app/modules/health/`
- Infraestructura de pruebas: `test/conftest.py`, `test/salud.http`

**Dependencias:**
- FastAPI, SQLModel, SQLAlchemy 2.0 (async), asyncpg, Alembic, pydantic-settings, bcrypt, PyJWT, uvicorn[standard], pytest, pytest-asyncio, httpx

**Notas:**
- Sin lógica de negocio
- Base de datos no requerida para `/health/live`
- La aplicación debe fallar rápido con error explícito si falta `JWT_SECRET`
- Todo el código con type hints en Python 3.12

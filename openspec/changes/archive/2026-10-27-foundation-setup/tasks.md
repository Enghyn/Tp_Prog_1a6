# Tareas

## 1. Configuración de estructura del proyecto
- [x] 1.1 Crear estructura de directorios: `app/`, `app/core/`, `app/modules/`, `app/modules/health/`, `app/modules/usuarios/`, `app/modules/clientes/`, `app/modules/repuestos/`, `app/modules/ordenes/`, `migrations/`, `test/` con archivos `__init__.py` en todos los paquetes Python - Verificar: todos los directorios existen con `__init__.py`

## 2. Dependencias y configuración
- [x] 2.1 Crear `requirements.txt` con versiones fijadas: FastAPI 0.111, SQLModel 0.0.24, SQLAlchemy 2.0, asyncpg 0.30, Alembic 1.13, pydantic-settings 2.0, bcrypt 4.0, PyJWT 2.8, uvicorn[standard], pytest, pytest-asyncio, httpx - Verificar: archivo existe con todas las dependencias
- [x] 2.2 Crear `app/core/config.py` con `Configuracion(BaseSettings)` conteniendo `database_url`, `jwt_secret`, `access_token_ttl_min`, `bcrypt_max_concurrency`, `login_max_intentos`, `login_ventana_seg`, `entorno` y validación fail-fast para `JWT_SECRET` faltante - Verificar: Configuracion carga correctamente y lanza error cuando falta JWT_SECRET
- [x] 2.3 Crear `.env.example` con todas las variables de configuración y añadir `.env` a `.gitignore` - Verificar: `.env.example` existe y `.gitignore` contiene `.env`

## 3. Inicialización de la aplicación
- [x] 3.1 Crear `main.py` con función `create_app()` retornando instancia FastAPI, context manager `lifespan` vacío preparado para hooks, configuración de logging estructurado y router raíz - Verificar: la app puede importarse y crearse
- [x] 3.2 Crear `app/modules/health/router.py` con endpoint `GET /health/live` retornando 200 sin acceder a base de datos - Verificar: el endpoint retorna 200

## 4. Infraestructura de pruebas
- [x] 4.1 Crear `test/conftest.py` con configuración de `httpx.AsyncClient` y `ASGITransport` para probar la app FastAPI - Verificar: conftest configura correctamente el cliente de pruebas
- [x] 4.2 Crear `test/salud.http` con ejemplos de solicitudes para el endpoint de salud - Verificar: archivo existe con ejemplos HTTP

## 5. Documentación y verificación
- [x] 5.1 Crear `README.md` con instrucciones de instalación, comandos para `uvicorn main:app --reload` y `pytest` - Verificar: README contiene las secciones requeridas
- [x] 5.2 Probar que `/health/live` retorna 200, la app falla rápido sin `JWT_SECRET`, y `/openapi.json` retorna 200 - Verificar: las tres pruebas pasan

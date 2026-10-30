# API Taller Mecánico

API REST para la gestión de un taller mecánico desarrollada con FastAPI, SQLModel y PostgreSQL.

## Tecnologías

- Python 3.12
- FastAPI 0.111
- SQLModel 0.0.24
- SQLAlchemy 2.0 (async)
- PostgreSQL 16
- Alembic 1.13
- asyncpg 0.30

## Instalación

1. Crear entorno virtual:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

2. Instalar dependencias:
```bash
pip install -r requirements.txt
```

3. Configurar variables de entorno:
```bash
cp .env.example .env
# Editar .env con tus valores
```

## Ejecución

```bash
uvicorn main:app --reload
```

La API estará disponible en `http://localhost:8000`
Documentación interactiva en `http://localhost:8000/docs`

## Pruebas

```bash
pytest tests/
```

La suite vive en `tests/` y se configura con `pytest.ini` (`testpaths = tests`, `asyncio_mode = strict`, `pythonpath = .`). Los tests de base de datos corren contra PostgreSQL real; definí `TEST_DATABASE_URL` (o `DATABASE_URL`) y `JWT_SECRET` antes de ejecutarlos.

## Datos iniciales

```bash
python seed.py                # carga idempotente
python seed.py --reset --si   # recrea el esquema con Alembic y vuelve a sembrar
```

`seed.py` es idempotente y transaccional. El flag `--reset` es destructivo y exige `--si`; en `entorno=produccion` el script aborta salvo que se pase `--forzar`.

También existe un espejo SQL manual:

```bash
psql "$DATABASE_URL" -f test/seed.sql
```

## Autenticación y Sesiones

El sistema gestiona la autenticación mediante JSON Web Tokens (JWT) emitidos en una cookie `HttpOnly` (`access_token`):

- **Login**: `POST /auth/login` con `email` y `password`. Devuelve `200` y establece la cookie `access_token`.
- **Sesión actual**: `GET /auth/yo` lee la cookie y devuelve usuario autenticado con sus roles vigentes en la base de datos (RN-04).
- **Logout**: `POST /auth/logout` borra la cookie `access_token`.
- **Atributos de la cookie**: `HttpOnly=True`, `SameSite=Lax`, `Path=/`, `Max-Age` derivado de `ACCESS_TOKEN_TTL_MIN` (en segundos).
- **Atributo Secure**:
  - Por defecto se deriva de `ENTORNO`: en `dev`, `local` y `test` es `False`; en `produccion` es `True`.
  - Puede fijarse explícitamente mediante `COOKIE_SECURE=true` o `COOKIE_SECURE=false`.
- **Límite de intentos (RN-08)**: Si se registran `LOGIN_MAX_INTENTOS` fallos para un `(email, ip)` en `LOGIN_VENTANA_SEG` segundos, la siguiente petición responde `429 Too Many Requests` con la cabecera `Retry-After` sin calcular hashes bcrypt.

### Credenciales de desarrollo

| Email | Rol | Contraseña |
|---|---|---|
| `admin@taller.local` | ADMIN | `Admin123!` |
| `recepcion@taller.local` | RECEPCION | `Recepcion123!` |
| `mecanico@taller.local` | MECANICO | `Mecanico123!` |
| `cliente@taller.local` | CLIENTE | `Cliente123!` |

> ⚠️ Estas credenciales son **solo para desarrollo local**. No deben usarse en producción ni en entornos compartidos. `mecanico@taller.local` se crea con `debe_cambiar_password = true`.

## Estructura del Proyecto

Ver [knowledge-base/02_descripcion_general.md](knowledge-base/02_descripcion_general.md) para más detalles.

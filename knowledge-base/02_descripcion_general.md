# 02 - Descripción General y Pila Tecnológica

## Dominio del Taller Mecánico
El sistema gestiona la actividad diaria de un taller mecánico:
- **Recepción**: Da de alta clientes y vehículos, y abre órdenes de trabajo describiendo la falla y los repuestos necesarios.
- **Mecánicos**: Toman órdenes de trabajo, ejecutan reparaciones y las dan por terminadas (descontando automáticamente el stock de repuestos).
- **Administradores**: Gestionan el catálogo de repuestos, reponen stock, administran personal y roles.
- **Clientes**: Se registran de forma autónoma en la web, consultan el estado de sus vehículos y órdenes, y pueden cancelar órdenes pendientes.

## Pila Tecnológica Obligatoria
| Componente | Versión Mínima | Uso en el Proyecto |
| :--- | :--- | :--- |
| **Python** | 3.12 | Lenguaje de programación base |
| **FastAPI** | 0.111 | Framework web asincrónico (`async def` en todos los handlers) |
| **SQLModel** | 0.0.24 | Definición unificada de modelos de tabla y Pydantic |
| **SQLAlchemy** | 2.0 (async) | Motor asincrónico, sesión y carga anticipada (`selectinload`) |
| **asyncpg** | 0.30 | Driver asincrónico de PostgreSQL |
| **PostgreSQL** | 16 | Motor de base de datos relacional |
| **Alembic** | 1.13 | Gestión de migraciones con plantilla asincrónica |
| **pydantic-settings**| 2.0 | Configuración leída desde variables de entorno o `.env` |
| **bcrypt** | 4.0 | Hashing seguro de contraseñas |
| **PyJWT** | 2.8 | Generación y verificación de tokens JWT firmados |
| **Uvicorn** | fastapi[standard] | Servidor ASGI |

## Estructura Obligatoria del Proyecto
Organización modular por dominio funcional con 6 capas estrictas:
- `main.py`: Aplicación FastAPI, lifespan (creación/cierre de motor, fábrica de sesiones, hash ficticio de login) y grupos de rutas.
- `seed.py`: Carga el estado inicial conocido de la base de datos (catálogo de estados, usuarios base, clientes, repuestos con stock inicial, órdenes de prueba, etc.).
- `app/core/`: Configuración (`config.py`), base de datos (`database.py`), seguridad (`security.py`), dependencias (`dependencies.py`), repositorios base (`repository.py`), paginación (`paginacion.py`) y Unit of Work base (`unit_of_work.py`).
- `app/modules/<módulo>/`: Módulos funcionales (`health`, `usuarios`, `clientes`, `repuestos`, `ordenes`) conteniendo `models.py`, `schemas.py`, `repository.py`, `unit_of_work.py`, `service.py` y `router.py`.
- `migrations/`: Configuración y versiones de Alembic.
- `test/`: Archivos `.http` para pruebas de integración y `solo_agregado.sql`.

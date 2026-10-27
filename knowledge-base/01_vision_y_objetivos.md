# 01 - Visión y Objetivos

## Visión del Proyecto
Desarrollar una API asincrónica robusta y segura para la gestión integral de talleres mecánicos (recepción de vehículos, asignación de órdenes de trabajo, control de stock de repuestos, autenticación basada en cookies HttpOnly y autorización basada en roles vigentes consultados en base de datos).

## Objetivos Educativos y Prácticos (UTN - Programación III)
El proyecto integra los conceptos desarrollados en los capítulos 1 a 6 de la materia:
1. **Fundamentos de FastAPI y contratos** (Capítulo 1 y 2): Endpoints asíncronos (`async def`), validación con Pydantic (`extra="forbid"`), códigos HTTP precisos (200, 201, 204, 401, 403, 404, 409, 422, 429).
2. **Ejecución asincrónica sin bloqueos** (Capítulo 3): Operaciones no bloqueantes, manejo de criptografía (`bcrypt`) fuera del bucle de eventos mediante `to_thread` con semáforo, y tareas en segundo plano (`BackgroundTasks`).
3. **Persistencia relacional y migraciones** (Capítulo 4): Modelos con SQLModel/SQLAlchemy 2.0, relaciones (asociación, composición, uno a uno opcional, catálogo), y migraciones asincrónicas gestionadas exclusivamente con Alembic (incluyendo migraciones escritas a mano para disparadores).
4. **Autenticación y Autorización** (Capítulo 5): Autenticación basada en JWT almacenado en cookies `HttpOnly`, protección contra fuerza bruta con límite de intentos (`intento_acceso`), control de roles vigentes en base de datos (`asignacion_rol`), cambio obligatorio de contraseña y separación en grupos de rutas.
5. **Repositorios, Unit of Work y Transacciones** (Capítulo 6): Jerarquía de repositorios (`BaseRepository`, `SoftDeleteRepository`), patrón Unit of Work asincrónico (gestor de contexto que confirma o revierte sin cerrar la sesión), y agrupación de transacciones complejas.
6. **Integridad de datos** (Capítulo 7): Disparadores (`TRIGGERS`) para tablas de sólo agregado (`historial_estado_orden`, `movimiento_stock`, `historial_precio_repuesto`) y restricciones en base de datos.

## Alcance (Qué entra y qué queda fuera)
- **Incluido**: API REST completa, autenticación, autorización por roles, UoW, transacciones atómicas para altas complejas y terminación de órdenes con descuento de stock, auditoría y disparadores.
- **Excluido**: Control de concurrencia avanzado (bloqueos pesimistas/optimistas, capítulo 7) y colas de tareas distribuidas con Redis (capítulo 8, reemplazado por `BackgroundTasks` simulado).

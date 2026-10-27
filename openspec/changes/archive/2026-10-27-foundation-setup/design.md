# Diseño

## Contexto

El API Taller Mecánico es un proyecto nuevo que sigue las especificaciones de la base de conocimiento. C-01 es el primer cambio de la secuencia y debe establecer la estructura base antes de que se puedan construir otros módulos.

## Objetivos / No Objetivos

**Objetivos:**
- Crear una estructura de proyecto limpia y modular siguiendo la arquitectura de 6 capas
- Configurar la gestión de configuración con pydantic-settings
- Establecer la inicialización de FastAPI con el patrón lifespan
- Proveer un endpoint de verificación de salud funcional
- Configurar la infraestructura de pruebas
- Fijar todas las dependencias a versiones específicas

**No Objetivos:**
- Modelos de base de datos o migraciones (se manejan en C-05/C-06/C-07)
- Autenticación/autorización (se manejan en cambios posteriores)
- Implementación de lógica de negocio
- Configuración Docker o despliegue

## Decisiones

### Decisión 1: Estructura del proyecto
**Opción elegida:** Seguir la estructura modular de 6 capas especificada en knowledge-base/02_descripcion_general.md
- `app/core/` para infraestructura compartida
- `app/modules/<modulo>/` con `models.py`, `schemas.py`, `repository.py`, `unit_of_work.py`, `service.py`, `router.py`
- `migrations/` para Alembic
- `test/` para pruebas y archivos `.http`

**Justificación:** Esta estructura es obligatoria según las especificaciones del proyecto.

### Decisión 2: Configuración con pydantic-settings
**Opción elegida:** Usar `Configuracion(BaseSettings)` con carga desde variables de entorno y soporte `.env`
**Justificación:** Provee configuración tipada, validación y gestión sencilla de entornos.

### Decisión 3: Patrón fábrica de aplicación
**Opción elegida:** Implementar `create_app()` retornando una instancia FastAPI configurada con `lifespan`
**Justificación:** Permite hooks de inicialización/finalización, mejor testabilidad y configuración limpia.

### Decisión 4: Endpoint de salud sin base de datos
**Opción elegida:** `GET /health/live` retorna 200 sin acceder a la base de datos
**Justificación:** Las sondas de vida deben ser independientes del estado de la base de datos.

### Decisión 5: Fallo rápido ante secretos faltantes
**Opción elegida:** La aplicación debe fallar rápido con error explícito si falta `JWT_SECRET` al iniciar
**Justificación:** Requisito de seguridad - no se permiten valores por defecto para secretos.

## Riesgos / Compromisos

- **Riesgo:** Archivos `__init__.py` faltantes → **Mitigación:** Crear todos los `__init__.py` necesarios
- **Riesgo:** Versiones de dependencias incorrectas → **Mitigación:** Fijar versiones exactas según especificación
- **Riesgo:** `.env` subido accidentalmente → **Mitigación:** Añadir `.env` a `.gitignore`, solo commitear `.env.example`
- **Compromiso:** Lifespan vacío ahora, más trabajo en C-05, pero mantiene C-01 enfocado solo en estructura

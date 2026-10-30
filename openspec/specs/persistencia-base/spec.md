# Especificación: persistencia-base

## Purpose

Administra la persistencia asíncrona mediante SQLAlchemy y asyncpg, proveyendo sesiones por solicitud sin commit implícito, ciclo de vida del motor de base de datos y soporte para migraciones de esquema.

## Requirements

### Requirement: Ciclo de vida del motor de base de datos
El sistema DEBE (SHALL) inicializar el motor asíncrono SQLAlchemy y el fabricante de sesiones con `expire_on_commit=False` durante el ciclo de vida de la aplicación (`lifespan`), almacenándolos en `app.state`, y DEBE liberar todas las conexiones con `engine.dispose()` durante el apagado.

#### Scenario: Inicialización exitosa del motor en lifespan
- **CUANDO** la aplicación inicia mediante su contexto de ciclo de vida (`lifespan`)
- **ENTONCES** el motor asíncrono y el generador de sesiones quedan disponibles en el estado de la aplicación

#### Scenario: Cierre controlado de conexiones al apagar la aplicación
- **CUANDO** la aplicación finaliza su ciclo de vida
- **ENTONCES** el motor asíncrono libera ordenadamente todas las conexiones activas del pool

### Requirement: Dependencia de sesión por request sin auto-commit
El sistema DEBE (SHALL) proveer una dependencia `get_session()` que entregue una `AsyncSession` por solicitud dentro de un contexto asíncrono garantizando su cierre y sin realizar commit automático en ningún momento.

#### Scenario: Obtención y cierre de sesión en petición HTTP
- **CUANDO** un endpoint utiliza la dependencia `get_session()`
- **ENTONCES** se entrega una sesión asíncrona abierta que se cierra automáticamente al finalizar el procesamiento del request

#### Scenario: Ausencia de commit implícito en la sesión
- **CUANDO** se utiliza la sesión entregada por `get_session()` y la solicitud finaliza sin errores
- **ENTONCES** la sesión nunca ejecuta `commit()` por su cuenta

### Requirement: Configuración asíncrona de migraciones Alembic
El sistema DEBE (SHALL) disponer de una configuración de Alembic basada en plantilla asíncrona para PostgreSQL, vinculada a la URL de base de datos de la configuración del sistema.

#### Scenario: Entorno de migraciones configurado
- **CUANDO** se invoca el entorno de Alembic
- **ENTONCES** el entorno carga la configuración asíncrona y resuelve la conexión mediante `database_url`

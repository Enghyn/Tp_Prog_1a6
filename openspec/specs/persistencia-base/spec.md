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

### Requirement: Columnas temporales con zona horaria
Toda columna temporal persistida SHALL usar `TIMESTAMP WITH TIME ZONE` (`timestamptz`); al releerla, el sistema SHALL devolver un `datetime` con `tzinfo` y el mismo instante absoluto que se escribió, sin depender del `TimeZone` de la sesión.

#### Scenario: Lectura de password_cambiada_en bajo zona horaria no-UTC
- **CUANDO** se persiste un `password_cambiada_en` UTC aware y se lee de vuelta en una sesión con `TimeZone = 'America/Buenos_Aires'`
- **ENTONCES** el valor leído es timezone-aware y representa exactamente el mismo instante UTC que el escrito, sin corrimiento de horas

#### Scenario: Lectura de evento_seguridad.cuando
- **CUANDO** se inserta un `evento_seguridad` y se lee su columna `cuando` desde la base
- **ENTONCES** el valor leído es timezone-aware y equivale al instante UTC persistido

### Requirement: Paridad entre modelos y migraciones
El esquema generado por las migraciones SHALL coincidir con el metadata de los modelos; `alembic check` SHALL finalizar sin operaciones nuevas, incluyendo la representación de la unicidad de `usuario.email`.

#### Scenario: Verificación de paridad limpia
- **CUANDO** se ejecuta `python -m alembic check` contra una base migrada a `head`
- **ENTONCES** el comando no detecta cambios de tipo, constraints ni índices y finaliza con éxito

#### Scenario: Unicidad de email estructuralmente equivalente
- **CUANDO** se compara el modelo `Usuario` con la tabla `usuario` creada por la migración `001_auth_core`
- **ENTONCES** ambos expresan la unicidad de `email` mediante una constraint única y no se reporta una diferencia de constraint frente a índice

### Requirement: Conservación del instante para comparaciones de sesión
Los valores temporales leídos de la base SHALL conservar el instante absoluto persistido, de modo que las comparaciones en Python (en particular la invalidación RN-07 por `password_cambiada_en`) no introduzcan desfase por zona horaria.

#### Scenario: Token emitido antes de un cambio de contraseña persistido
- **CUANDO** un token con `iat` diez minutos anterior a un `password_cambiada_en` persistido se presenta en `GET /auth/yo`
- **ENTONCES** el sistema responde `401` aunque la firma y `exp` sean válidos

#### Scenario: Token emitido después de un cambio de contraseña persistido
- **CUANDO** un token con `iat` posterior al `password_cambiada_en` persistido se presenta en `GET /auth/yo`
- **ENTONCES** el sistema resuelve la sesión y responde `200`

### Requirement: Prohibición de columnas DateTime naive
El metadata de los modelos SHALL declarar todas sus columnas `DateTime` con `timezone=True`; una verificación automatizada SHALL fallar si aparece una columna temporal naive.

#### Scenario: Verificación de metadata sin columnas naive
- **CUANDO** se recorren todas las columnas `DateTime` del metadata de SQLModel
- **ENTONCES** cada una declara `timezone=True` y la verificación pasa

#### Scenario: Columna naive detectada
- **CUANDO** se agrega un campo `datetime` sin `timezone=True` a cualquier modelo
- **ENTONCES** la verificación automatizada falla e identifica la tabla y columna infractoras

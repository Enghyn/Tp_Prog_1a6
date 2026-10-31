# Spec Delta

## ADDED Requirements

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

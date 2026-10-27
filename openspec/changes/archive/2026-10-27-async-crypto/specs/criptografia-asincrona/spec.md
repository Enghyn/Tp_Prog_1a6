# Delta de Especificación

## Propósito

Provee utilidades de criptografía para contraseñas que no bloquean el event loop, con protección contra enumeración de usuarios mediante respuestas con tiempo constante.

## REQUISITOS AGREGADOS

### Requisito: Hash de contraseñas asíncrono
El sistema DEBE proveer funciones `hash_password()` y `verify_password()` que ejecuten bcrypt en un thread separado usando `asyncio.to_thread`, protegidas por un semáforo para limitar la concurrencia.

#### Escenario: Hash y verificación correctos
- **CUANDO** se llama a `hash_password()` con una contraseña
- **ENTONCES** se genera un hash verificable con `verify_password()`

#### Escenario: Múltiples verificaciones concurrentes
- **CUANDO** se realizan 20 verificaciones concurrentes
- **ENTONCES** el event loop no se bloquea y la concurrencia está limitada por el semáforo

### Requisito: Hash síncrono para seed
El sistema DEBE proveer `hash_password_sync()` para uso exclusivo de `seed.py` o CLI, documentando que nunca debe usarse dentro de un handler async.

#### Escenario: Uso en script externo
- **CUANDO** se usa `hash_password_sync()` fuera del event loop
- **ENTONCES** genera un hash bcrypt válido

### Requisito: Protección contra enumeración de usuarios
El sistema DEBE generar un hash ficticio al iniciar la aplicación y proveer `verify_password_o_dummy()` para mantener tiempo de respuesta constante independientemente de si el usuario existe (RN-09).

#### Escenario: Usuario inexistente
- **CUANDO** se verifica una contraseña para un usuario inexistente usando el hash ficticio
- **ENTONCES** la función retorna `False` pero toma tiempo similar a una verificación real

#### Escenario: Usuario inexistente retorna falso
- **CUANDO** se llama a `verify_password_o_dummy()` con hash nulo
- **ENTONCES** siempre retorna `False`

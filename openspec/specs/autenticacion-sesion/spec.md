# autenticacion-sesion Specification

## Purpose
Define cómo la API emite, transporta y valida sesiones autenticadas con JWT en cookie HttpOnly, cómo limita los intentos de login fallidos y cómo audita cada acceso en las tablas de seguridad.

## Requirements

### Requirement: Inicio de sesión con credenciales válidas

`POST /auth/login` SHALL aceptar únicamente `email` y `password` y, ante credenciales válidas de un usuario activo, SHALL responder `200` con el usuario, sus roles vigentes y los claims `iat`/`exp`, estableciendo la cookie de sesión `access_token`.

#### Scenario: Cookie de sesión con los atributos exigidos

- **CUANDO** un usuario activo se autentica con la contraseña correcta
- **ENTONCES** la respuesta `200` incluye `Set-Cookie` de `access_token` con `HttpOnly`, `SameSite=Lax`, `Path=/`, `Max-Age` igual al TTL configurado y `Secure` según el entorno

#### Scenario: Cuerpo de respuesta con la sesión emitida

- **CUANDO** el login es exitoso
- **ENTONCES** el cuerpo incluye el id y email del usuario, sus roles vigentes y los valores `iat` y `exp` del token emitido, sin exponer `password_hash`

#### Scenario: Contrato de entrada estricto

- **CUANDO** el cuerpo incluye un campo no declarado, el email no es válido, la contraseña está vacía o supera el máximo admitido por bcrypt
- **ENTONCES** el sistema responde `422` con el formato uniforme de error y no emite cookie

### Requirement: Login opaco ante credenciales inválidas

El sistema SHALL responder `401` con cuerpo y código idénticos cuando el email no existe, la contraseña es incorrecta o el usuario está inactivo, y SHALL ejecutar una verificación bcrypt de costo equivalente en los tres casos, usando el hash ficticio cuando no hay usuario (RN-09).

#### Scenario: Email inexistente y contraseña incorrecta son indistinguibles

- **CUANDO** se intenta login con un email no registrado y con un email registrado con contraseña errónea
- **ENTONCES** ambas respuestas tienen el mismo código `401`, el mismo `detail` y el mismo `codigo`, sin diferencias de formato ni de campos

#### Scenario: Usuario inactivo rechazado de forma uniforme

- **CUANDO** las credenciales corresponden a un usuario con `activo=false`
- **ENTONCES** el sistema responde `401` con el mismo cuerpo que un fallo de contraseña y no emite cookie

#### Scenario: Respuesta de error sin cookie

- **CUANDO** el login falla por cualquier motivo de credenciales
- **ENTONCES** la respuesta no incluye `Set-Cookie` de `access_token`

### Requirement: Límite de intentos fallidos por email e IP

El sistema SHALL contar los registros de `intento_acceso` fallidos por `(email, ip)` dentro de los últimos `login_ventana_seg` segundos y, cuando el conteo sea mayor o igual a `login_max_intentos`, SHALL responder `429` con la cabecera `Retry-After` en segundos, sin ejecutar bcrypt ni consultar el hash del usuario (RN-08).

#### Scenario: Petición bloqueada tras agotar los intentos

- **CUANDO** existen `login_max_intentos` intentos fallidos registrados para el mismo `(email, ip)` dentro de la ventana y llega una nueva petición de login
- **ENTONCES** el sistema responde `429`, incluye `Retry-After` con los segundos restantes de la ventana y no calcula ni verifica ningún hash

#### Scenario: El intento que alcanza el límite todavía se verifica

- **CUANDO** llega un intento cuando el conteo previo es `login_max_intentos - 1` e inválido
- **ENTONCES** el sistema responde `401`, registra el intento fallido y deja el conteo en `login_max_intentos`

#### Scenario: El bloqueo expira al cerrarse la ventana

- **CUANDO** se espera el tiempo indicado en `Retry-After` y la ventana ya no contiene `login_max_intentos` fallos
- **ENTONCES** el sistema vuelve a procesar el login con verificación normal en lugar de responder `429`

#### Scenario: El bloqueo no se extiende a sí mismo

- **CUANDO** una petición bloqueada con `429` se repite varias veces
- **ENTONCES** el conteo de fallos no crece por esas peticiones y el bloqueo termina al cumplirse la ventana original

### Requirement: Firma y contenido del token de sesión

El sistema SHALL emitir un JWT firmado con HS256 y el secreto configurado, con `sub` igual al id del usuario, `iat` con precisión de microsegundos, `exp` igual a `iat` más el TTL configurado y `roles` informativos con los roles vigentes al momento de emitir (RN-04).

#### Scenario: Claims del token emitido

- **CUANDO** se emite un token para un usuario con roles vigentes
- **ENTONCES** el token contiene `sub`, `iat`, `exp` y `roles`, y su algoritmo declarado es HS256

#### Scenario: Token con algoritmo no permitido rechazado

- **CUANDO** se presenta un token firmado con un algoritmo distinto de HS256 o con firma inválida
- **ENTONCES** el sistema responde `401` y no intenta decodificarlo con otro algoritmo

#### Scenario: Precisión de microsegundos en iat

- **CUANDO** se emite un token
- **ENTONCES** `iat` conserva microsegundos al serializarse y al leerse de vuelta, sin truncarse a segundos

### Requirement: Resolución de la sesión en peticiones protegidas

Toda petición autenticada SHALL resolver al usuario a partir de la cookie `access_token` y SHALL responder `401` cuando la cookie falta, el token no verifica, `exp` ya pasó o el usuario dejó de estar activo.

#### Scenario: Petición sin cookie

- **CUANDO** se invoca un endpoint protegido sin cookie `access_token`
- **ENTONCES** el sistema responde `401` con el formato uniforme de error

#### Scenario: Token manipulado

- **CUANDO** la cookie contiene un token con la firma alterada
- **ENTONCES** el sistema responde `401` y no resuelve ningún usuario

#### Scenario: Token expirado

- **CUANDO** la cookie contiene un token cuyo `exp` está en el pasado
- **ENTONCES** el sistema responde `401`

#### Scenario: Usuario desactivado después de emitir el token

- **CUANDO** el token es válido pero el usuario asociado tiene `activo=false` al momento de la petición
- **ENTONCES** el sistema responde `401`

### Requirement: Invalidación de sesiones por cambio de contraseña

El sistema SHALL rechazar con `401` todo token cuyo `iat` sea estrictamente anterior a `usuario.password_cambiada_en`, comparando con precisión de microsegundos y sin truncar fracciones de segundo, y SHALL aceptar los tokens emitidos en o después de ese instante (RN-07).

#### Scenario: Token anterior al cambio de contraseña

- **CUANDO** el usuario cambió su contraseña después de que se emitió el token presentado
- **ENTONCES** el sistema responde `401` aunque la firma y `exp` sean válidos

#### Scenario: Token emitido después del cambio

- **CUANDO** el token fue emitido después de `password_cambiada_en`
- **ENTONCES** la petición se procesa normalmente

#### Scenario: Diferencia dentro del mismo segundo

- **CUANDO** `iat` y `password_cambiada_en` caen en el mismo segundo y difieren sólo en microsegundos, con `iat` anterior
- **ENTONCES** el sistema responde `401`, sin redondear ni truncar los timestamps

### Requirement: Consulta de la sesión actual con roles vigentes

`GET /auth/yo` SHALL responder `200` con el usuario autenticado, los roles leídos de `asignacion_rol` en el momento de la petición y los valores `iat`/`exp` del token, considerando sólo asignaciones con `revocada_en IS NULL` y `vence_en` nulo o futuro.

#### Scenario: Roles vigentes devueltos

- **CUANDO** un usuario autenticado consulta su sesión
- **ENTONCES** la respuesta lista los roles de sus asignaciones abiertas y no vencidas

#### Scenario: Rol revocado deja de aparecer

- **CUANDO** una asignación fue revocada después de emitirse el token
- **ENTONCES** `GET /auth/yo` ya no incluye ese rol en la respuesta

#### Scenario: Los roles del token no se usan para responder

- **CUANDO** el token contiene un rol que el usuario no tiene vigente en la base
- **ENTONCES** la respuesta no incluye ese rol

### Requirement: Cierre de sesión idempotente

`POST /auth/logout` SHALL eliminar la cookie `access_token` y SHALL responder `200`, incluso cuando la cookie no está presente o el token ya no es válido.

#### Scenario: Logout elimina la cookie

- **CUANDO** se invoca el logout con una cookie de sesión presente
- **ENTONCES** la respuesta `200` incluye una instrucción de borrado de `access_token` con el mismo `Path` y los mismos atributos de seguridad

#### Scenario: Logout sin sesión previa

- **CUANDO** se invoca el logout sin cookie o con un token inválido
- **ENTONCES** el sistema responde `200` sin error

#### Scenario: El token copiado sobrevive al logout

- **CUANDO** un token fue copiado antes del logout y se reutiliza después
- **ENTONCES** sigue siendo válido hasta su `exp`, porque la revocación sólo ocurre por cambio de contraseña (RN-07)

### Requirement: Cambio de contraseña autenticado

`POST /auth/cambiar-password` SHALL exigir una sesión válida y aceptar únicamente `password_actual` y `password_nueva`. Con la contraseña actual correcta y una nueva que cumpla la política, SHALL responder `200`, persistir el nuevo hash, fijar `password_cambiada_en` con microsegundos y `debe_cambiar_password=false`, sin reemitir la cookie de sesión (RN-06, RN-07).

#### Scenario: Cambio exitoso persiste el nuevo estado

- **WHEN** un usuario autenticado envía su contraseña actual correcta y una contraseña nueva válida
- **THEN** el sistema responde `200`, el `password_hash` almacenado verifica contra la nueva contraseña, `password_cambiada_en` queda en el instante del cambio sin truncar microsegundos y `debe_cambiar_password` queda en `false`

#### Scenario: La respuesta no reemite la cookie de sesión

- **WHEN** el cambio de contraseña es exitoso
- **THEN** la respuesta `200` no incluye un `Set-Cookie` con un token nuevo, porque el token usado para la petición queda inválido por RN-07

#### Scenario: Usuario con contraseña provisoria puede cambiar

- **WHEN** un usuario con `debe_cambiar_password=true` invoca el endpoint con una cookie válida
- **THEN** la petición se procesa (no responde `403`) y, si el cambio es exitoso, la bandera queda en `false`

#### Scenario: El token anterior deja de ser válido

- **WHEN** el usuario cambia su contraseña y luego reutiliza el token con el que hizo la petición
- **THEN** el sistema responde `401` en la siguiente petición protegida, porque su `iat` es anterior a `password_cambiada_en`

#### Scenario: Un token emitido después del cambio es válido

- **WHEN** el usuario vuelve a autenticarse con la contraseña nueva y usa el token recién emitido
- **THEN** la petición protegida se procesa normalmente

### Requirement: Rechazo del cambio de contraseña

El sistema SHALL responder `401` uniforme cuando `password_actual` no verifica, sin persistir ningún cambio. SHALL responder `422` cuando falte un campo, se envíe un campo no declarado, `password_nueva` quede fuera de 8–72 caracteres, no incluya mayúscula, minúscula y dígito, o sea igual a `password_actual`.

#### Scenario: Contraseña actual incorrecta

- **WHEN** el usuario envía una `password_actual` que no verifica contra su hash
- **THEN** el sistema responde `401` con el cuerpo y código uniformes de credenciales inválidas, y el hash, `password_cambiada_en` y `debe_cambiar_password` permanecen sin cambios

#### Scenario: Contrato de entrada estricto

- **WHEN** el cuerpo omite `password_actual` o `password_nueva`, o incluye un campo no declarado
- **THEN** el sistema responde `422` con el formato uniforme de error y no modifica la contraseña

#### Scenario: Longitud fuera de rango

- **WHEN** `password_nueva` tiene menos de 8 o más de 72 caracteres
- **THEN** el sistema responde `422` y no modifica la contraseña

#### Scenario: Complejidad insuficiente

- **WHEN** `password_nueva` no contiene al menos una mayúscula, una minúscula y un dígito
- **THEN** el sistema responde `422` y no modifica la contraseña

#### Scenario: La contraseña nueva repite la actual

- **WHEN** `password_nueva` es igual a `password_actual`
- **THEN** el sistema responde `422` y no modifica la contraseña

#### Scenario: Petición sin sesión

- **WHEN** se invoca el endpoint sin cookie `access_token` válida
- **THEN** el sistema responde `401` antes de evaluar el cuerpo

#### Scenario: La respuesta 422 no repite las contraseñas

- **WHEN** el cuerpo del cambio de contraseña falla la validación
- **THEN** la respuesta `422` lista los campos y mensajes de error sin incluir `password_actual` ni `password_nueva` en el cuerpo

### Requirement: Auditoría de acceso en transacción independiente

El sistema SHALL registrar cada intento de login en `intento_acceso` y cada evento de seguridad en `evento_seguridad` (`LOGIN_OK`, `LOGIN_FALLIDO`, `LOGIN_BLOQUEADO`, `LOGOUT`, `PASSWORD_CAMBIADA`) dentro de una transacción independiente que SHALL confirmarse aunque la petición termine en error.

#### Scenario: Login fallido deja rastro persistido

- **WHEN** un login falla por credenciales inválidas
- **THEN** el intento queda persistido con `exito=false` y el evento `LOGIN_FALLIDO` queda registrado, pese a que la petición responde `401`

#### Scenario: Login exitoso auditado

- **WHEN** un login es exitoso
- **THEN** se persiste un intento con `exito=true` y el evento `LOGIN_OK`

#### Scenario: Bloqueo auditado sin sumar fallos

- **WHEN** una petición es rechazada por límite de intentos
- **THEN** se registra el evento `LOGIN_BLOQUEADO` y no se inserta un nuevo intento fallido

#### Scenario: Logout auditado

- **WHEN** el logout identifica una sesión válida
- **THEN** se registra el evento `LOGOUT` con el usuario como actor

#### Scenario: Cambio de contraseña auditado

- **WHEN** un cambio de contraseña es exitoso
- **THEN** se registra el evento `PASSWORD_CAMBIADA` con el email del usuario como actor y el instante del cambio, sin insertar una fila en `intento_acceso`

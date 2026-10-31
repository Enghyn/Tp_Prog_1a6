# autorizacion-rbac Specification

## Purpose
Define cómo la API decide permisos en cada petición a partir de los roles vigentes en la base de datos, cómo exige roles por grupo de rutas, cómo verifica la propiedad de recursos del cliente y cómo restringe a los usuarios con contraseña pendiente de cambio.

## Requirements

### Requirement: Roles vigentes releídos de la base en cada petición

Toda decisión de autorización SHALL consultar `asignacion_rol` en el momento de la petición, considerando únicamente las asignaciones con `revocada_en IS NULL` y `vence_en` nulo o posterior al instante actual. Los roles incluidos en el token JWT SHALL NOT otorgar ni mantener permisos (RN-04).

#### Scenario: Rol revocado en caliente pierde acceso en la petición siguiente

- **CUANDO** un usuario con rol `RECEPCION` vigente invoca una ruta que exige `RECEPCION` y luego su asignación se revoca con `revocada_en` en el presente
- **ENTONCES** la primera petición responde con éxito y la siguiente, con el mismo token aún no expirado, responde `403`

#### Scenario: Asignación vencida no autoriza

- **CUANDO** el usuario presenta un token válido pero su única asignación del rol exigido tiene `vence_en` en el pasado
- **ENTONCES** el sistema responde `403` y no considera vigente esa asignación

#### Scenario: Rol presente sólo en el token no autoriza

- **CUANDO** el token declara un rol que ya no existe como asignación vigente en la base
- **ENTONCES** el sistema responde `403` en una ruta que exige ese rol

#### Scenario: Rol concedido en caliente habilita sin reemitir el token

- **CUANDO** al usuario se le asigna un rol nuevo después de emitirse su token y el token no lo declara
- **ENTONCES** la siguiente petición a una ruta que exige ese rol se autoriza

#### Scenario: Rol vigente sin vencimiento autoriza

- **CUANDO** la asignación del rol exigido tiene `vence_en` nulo y `revocada_en` nulo
- **ENTONCES** el sistema considera el rol vigente y autoriza la petición

### Requirement: Distinción entre falta de credencial y falta de rol

Una ruta que exige roles SHALL responder `401` cuando no hay credencial válida y `403` cuando la credencial es válida pero el usuario no posee ninguno de los roles exigidos, usando el formato uniforme de error `{"detail", "codigo"}`.

#### Scenario: Sin cookie de sesión

- **CUANDO** se invoca una ruta que exige roles sin cookie `access_token`
- **ENTONCES** el sistema responde `401` con `codigo` de credenciales inválidas

#### Scenario: Token inválido o expirado

- **CUANDO** la cookie contiene un token con firma inválida, `exp` vencido o usuario inactivo
- **ENTONCES** el sistema responde `401` y no evalúa roles

#### Scenario: Credencial válida sin el rol exigido

- **CUANDO** un usuario autenticado sin ninguno de los roles exigidos invoca la ruta
- **ENTONCES** el sistema responde `403` con un `codigo` que identifica la falta de permisos, sin revelar qué roles tiene el usuario

#### Scenario: Credencial válida con uno de los roles exigidos

- **CUANDO** el usuario autenticado posee vigente al menos uno de los roles exigidos por la ruta
- **ENTONCES** la petición se procesa normalmente

#### Scenario: Ruta que exige varios roles acepta cualquiera de ellos

- **CUANDO** una ruta exige `ADMIN` o `RECEPCION` y el usuario tiene vigente sólo `RECEPCION`
- **ENTONCES** la petición se autoriza

### Requirement: Separación entre grupo de rutas públicas y protegidas

El sistema SHALL montar las rutas en dos grupos: uno público con `/health/*`, `/auth/registro`, `/auth/login` y `/auth/logout`, y uno protegido con todas las demás rutas, incluido `/auth/yo`. Pertenecer al grupo protegido SHALL implicar exigir una sesión válida, sin que cada endpoint deba declararlo (RN-06).

#### Scenario: Ruta pública accesible sin sesión

- **CUANDO** se invoca `GET /health/live`, `GET /health/ready`, `POST /auth/registro`, `POST /auth/login` o `POST /auth/logout` sin cookie de sesión
- **ENTONCES** el sistema no responde `401` por falta de credencial y procesa la petición según su propio contrato

#### Scenario: Ruta del grupo protegido sin sesión

- **CUANDO** se invoca una ruta del grupo protegido sin cookie de sesión
- **ENTONCES** el sistema responde `401` antes de ejecutar la lógica del endpoint

#### Scenario: Ruta de autenticación autenticada sigue disponible

- **CUANDO** se invoca `GET /auth/yo` o `POST /auth/logout` con cookie válida
- **ENTONCES** la petición se procesa y no se bloquea por pertenecer a `/auth/*`

### Requirement: Bloqueo de rutas de dominio con contraseña pendiente

Cuando `usuario.debe_cambiar_password` es verdadero, el sistema SHALL responder `403` en toda ruta del grupo protegido que no pertenezca a `/auth/*` ni a `/health/*`, y SHALL permitir las rutas de autenticación y salud (RN-06).

#### Scenario: Usuario con contraseña provisoria bloqueado en rutas de dominio

- **CUANDO** un usuario autenticado con `debe_cambiar_password=true` invoca una ruta protegida que no es `/auth/*` ni `/health/*`
- **ENTONCES** el sistema responde `403` con un `codigo` que identifica la contraseña pendiente y no ejecuta el endpoint

#### Scenario: Usuario con contraseña provisoria habilitado en rutas de autenticación

- **CUANDO** el mismo usuario invoca `GET /auth/yo` o `POST /auth/logout`
- **ENTONCES** la petición se procesa normalmente y la respuesta refleja `debe_cambiar_password=true`

#### Scenario: Rutas de salud no se bloquean

- **CUANDO** un usuario con contraseña pendiente invoca `GET /health/live` o `GET /health/ready`
- **ENTONCES** el sistema responde según el contrato de salud, sin `403` por contraseña pendiente

#### Scenario: El bloqueo se levanta al cambiar la contraseña

- **CUANDO** el usuario completa el cambio de contraseña y la bandera queda en `false`
- **ENTONCES** la siguiente petición a una ruta de dominio con un token válido se procesa normalmente

#### Scenario: El bloqueo no depende del token

- **CUANDO** el token fue emitido cuando la bandera estaba en `false` y la bandera se activa después
- **ENTONCES** la siguiente petición a una ruta de dominio responde `403`, porque el estado se lee de la base

### Requirement: Verificación de propiedad de vehículo

El sistema SHALL ofrecer una verificación de propiedad que determine si un vehículo pertenece al cliente vinculado a un usuario autenticado, siguiendo `vehiculo.cliente_id → cliente.usuario_id`, para que las rutas del cliente apliquen RN-17.

#### Scenario: Vehículo del cliente autenticado

- **CUANDO** el vehículo pertenece a la ficha de cliente cuyo `usuario_id` es el del usuario autenticado
- **ENTONCES** la verificación de propiedad resulta verdadera

#### Scenario: Vehículo de otro cliente

- **CUANDO** el vehículo pertenece a la ficha de cliente de otro usuario
- **ENTONCES** la verificación de propiedad resulta falsa y el endpoint responde `403`

#### Scenario: Vehículo inexistente

- **CUANDO** el identificador de vehículo no existe
- **ENTONCES** la verificación de propiedad resulta falsa y no se confunde con una autorización concedida

#### Scenario: Usuario sin ficha de cliente

- **CUANDO** el usuario autenticado no tiene ficha en `cliente`
- **ENTONCES** la verificación de propiedad resulta falsa para cualquier vehículo

### Requirement: Verificación de propiedad de orden de trabajo

El sistema SHALL ofrecer una verificación de propiedad que determine si una orden de trabajo corresponde al cliente vinculado a un usuario autenticado, siguiendo `orden_trabajo.vehiculo_id → vehiculo.cliente_id → cliente.usuario_id`, para que las rutas `/mis-ordenes` y la cancelación por dueño apliquen RN-17.

#### Scenario: Orden sobre un vehículo del cliente autenticado

- **CUANDO** la orden referencia un vehículo de la ficha de cliente del usuario autenticado
- **ENTONCES** la verificación de propiedad resulta verdadera

#### Scenario: Orden de otro cliente

- **CUANDO** la orden referencia un vehículo de la ficha de cliente de otro usuario
- **ENTONCES** la verificación de propiedad resulta falsa y el endpoint responde `403`

#### Scenario: Orden inexistente

- **CUANDO** el identificador de orden no existe
- **ENTONCES** la verificación de propiedad resulta falsa y no se confunde con una autorización concedida

#### Scenario: Asignación como mecánico no otorga propiedad

- **CUANDO** el usuario autenticado es el mecánico asignado a la orden pero no es el cliente dueño del vehículo
- **ENTONCES** la verificación de propiedad resulta falsa; el acceso del mecánico se decide por rol y estado de la orden, no por esta verificación

# 07 - Flujos Principales de Operación

## 1. Flujo de Auto-Registro (RN-02)
1. El usuario envía `POST /auth/registro` con datos de cuenta y cliente.
2. El servicio abre un único bloque de `UnitOfWork`.
3. Se crea el usuario (con hash de contraseña calculado fuera del bucle), se le asigna el rol `CLIENTE` en `asignacion_rol`, y se crea la ficha en `cliente`.
4. Si ocurre cualquier fallo (ej. documento duplicado), se realiza `rollback` completo de las tres escrituras.

## 2. Flujo de Autenticación y Login (RN-08, RN-09)
1. Petición a `POST /auth/login`.
2. Se verifica el límite de intentos (`intento_acceso` en los últimos 60 segundos). Si supera 5 intentos fallidos, responde `429 Too Many Requests` con cabecera `Retry-After` sin calcular hash.
3. Se busca el usuario por correo. Si no existe, se ejecuta verificación contra un hash ficticio para mantener tiempo de respuesta constante (prevención de enumeración).
4. Se verifica el hash con `bcrypt` (en hilo separado mediante `to_thread` con semáforo).
5. Se emite un JWT firmado con `sub`, `iat`, `exp` y los roles vigentes.
6. Se establece la cookie `access_token` con atributos `HttpOnly`, `SameSite=Lax`.

## 3. Flujo de Apertura y Terminación de Órdenes de Trabajo (RN-10, RN-13)
1. **Apertura (`POST /ordenes`)**: Se validan los ítems, se copian los precios unitarios actuales de los repuestos, se calcula el total en el servidor, y se crea la orden en estado `PENDIENTE` junto con su línea inicial en `historial_estado_orden`.
2. **Inicio (`POST /ordenes/{id}/iniciar`)**: El mecánico asigna la orden y pasa a `EN_REPARACION`.
3. **Terminación (`POST /ordenes/{id}/terminar`)**: 
   - El servicio abre un `UnitOfWork`.
   - Verifica el stock disponible de cada repuesto asociado en `item_orden`.
   - Si algún repuesto no alcanza, la transacción se revierte y responde `409 Conflict`.
   - Si hay stock suficiente, se descuenta el stock de cada repuesto, se registran los movimientos de salida en `movimiento_stock`, se actualiza el estado de la orden a `TERMINADA`, y se añade la línea correspondiente en `historial_estado_orden`.
   - Tras confirmar la transacción exitosamente, se agenda una tarea en segundo plano (`BackgroundTasks`) con `await asyncio.sleep(0.5)` para simular el aviso al cliente.

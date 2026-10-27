# Diseño

## Contexto

C-01 estableció la base. C-02 estableció los contratos HTTP. Ahora se necesita implementar la criptografía no bloqueante para autenticación.

## Objetivos / No Objetivos

**Objetivos:**
- Implementar hash de contraseñas sin bloquear el event loop
- Proteger contra enumeración de usuarios con tiempo de respuesta constante
- Proveer hash síncrono para uso en seed/scripts
- Limitar la concurrencia de operaciones bcrypt

**No Objetivos:**
- Implementar autenticación JWT (C-09)
- Implementar endpoints de login (C-09)

## Decisiones

### Decisión 1: Usar asyncio.to_thread
**Opción elegida:** Envolver llamadas a bcrypt en `asyncio.to_thread()`
**Justificación:** bcrypt es CPU-intensivo y bloqueante. to_thread lo ejecuta en thread pool sin bloquear el event loop.

### Decisión 2: Semáforo para limitar concurrencia
**Opción elegida:** Crear `asyncio.Semaphore` en `lifespan` y guardarlo en `app.state`
**Justificación:** bcrypt es costoso computacionalmente. Limitar concurrencia evita saturar CPU.

### Decisión 3: Hash ficticio para protección contra enumeración
**Opción elegida:** Generar hash ficticio al iniciar y usarlo cuando usuario no existe
**Justificación:** RN-09 requiere tiempo de respuesta constante para evitar que un atacante determine si un email existe.

### Decisión 4: Separar hash síncrono
**Opción elegida:** `hash_password_sync()` separado de la versión async
**Justificación:** Úsalo solo en contextos sin event loop (seed, scripts CLI). Nunca en handlers async.

## Riesgos / Compromisos

- **Riesgo:** Semáforo mal configurado puede limitar demasiado → **Mitigación:** Configurable via `bcrypt_max_concurrency`
- **Riesgo:** Generación de hash ficticio al inicio puede agregar latencia → **Mitigación:** Es aceptable, solo ocurre una vez al arrancar
- **Compromiso:** Complejidad adicional vs simplicidad, pero necesario para cumplir RN-09

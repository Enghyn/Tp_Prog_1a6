# Propuesta

## ¿Por qué?

La autenticación requiere hash de contraseñas seguro sin bloquear el event loop de FastAPI. Además, el flujo de login debe ser resistente a enumeración de usuarios (RN-09) usando un hash ficticio con tiempo de respuesta constante. Este cambio implementa las utilidades criptográficas reutilizables por autenticación y seed.

## ¿Qué cambios?

- **Seguridad asíncrona**: Crear `app/core/seguridad.py` con `hash_password()` / `verify_password()` envolviendo `bcrypt` en `asyncio.to_thread`, protegidos por `asyncio.Semaphore` creado en `lifespan` (`app.state`)
- **Hash síncrono para seed**: Añadir `hash_password_sync()` exclusivo para `seed.py`/CLI (nunca usarlo en handlers)
- **Protección contra enumeración**: Implementar `generar_hash_ficticio()` al arrancar y `verify_password_o_dummy()` con tiempo de respuesta constante (RN-09)
- **Integración con lifespan**: Inicializar semáforo y hash ficticio en `main.py`

## Capacidades

### Nuevas Capacidades
- `criptografia-asincrona`: Utilidades de hash de contraseñas no bloqueantes con protección contra enumeración de usuarios

### Capacidades Modificadas
<!-- Sin capacidades existentes para modificar -->

## Impacto

**Áreas afectadas:**
- `app/core/seguridad.py` (nuevo)
- `main.py` (lifespan)
- Uso futuro por C-08 (seed) y C-09 (login)

**Dependencias:** C-01

**Notas:**
- Debe seguir RN-09
- Nunca ejecutar bcrypt directamente en el event loop
- El semáforo debe limitar la concurrencia de operaciones bcrypt
- `hash_password_sync()` solo para uso fuera de handlers async

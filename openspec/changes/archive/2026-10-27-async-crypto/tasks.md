# Tareas

## 1. Módulo de seguridad
- [x] 1.1 Crear `app/core/seguridad.py` con `hash_password()` y `verify_password()` usando `asyncio.to_thread` y semáforo desde `app.state` - Verificar: funciones async implementadas correctamente
- [x] 1.2 Añadir `hash_password_sync()` para uso exclusivo en seed/CLI - Verificar: función síncrona funciona fuera del event loop
- [x] 1.3 Implementar `generar_hash_ficticio()` y `verify_password_o_dummy()` con tiempo de respuesta constante - Verificar: retorna False para hash nulo y usa hash ficticio

## 2. Integración con la aplicación
- [x] 2.1 Modificar `main.py` para inicializar semáforo bcrypt en `lifespan` y guardarlo en `app.state`, generar hash ficticio al iniciar - Verificar: semáforo y hash ficticio disponibles en app.state
- [x] 2.2 Añadir constantes/configuración necesarias si aplica - Verificar: configuración correcta

## 3. Pruebas
- [x] 3.1 Crear pruebas: 20 verificaciones concurrentes no bloquean el event loop, semáforo limita concurrencia, hash ficticio siempre retorna False - Verificar: todas las pruebas pasan
- [x] 3.2 Crear prueba: `hash_password()` produce hashes verificables con `verify_password()` - Verificar: hash y verificación funcionan correctamente

# Delta de Especificación

## Propósito

Provee un endpoint de verificación de vida para la API sin necesidad de conectividad a la base de datos, permitiendo monitorear la disponibilidad básica del servicio.

## REQUISITOS AGREGADOS

### Requisito: Endpoint de verificación de vida
El sistema DEBE exponer un endpoint `GET /health/live` que retorne HTTP 200 sin acceder a la base de datos.

#### Escenario: Verificación exitosa de vida
- **CUANDO** un cliente realiza una solicitud GET a `/health/live`
- **ENTONCES** el sistema retorna HTTP 200 con una respuesta exitosa

### Requisito: Inicialización de la aplicación
El sistema DEBE proveer una fábrica de aplicación FastAPI con logging estructurado y un contexto de ciclo de vida preparado para futuros hooks de inicialización.

#### Escenario: Creación de la aplicación
- **CUANDO** se llama a `create_app()`
- **ENTONCES** se retorna una instancia de FastAPI configurada con logging y ciclo de vida adjuntado

### Requisito: Carga de configuración
El sistema DEBE cargar la configuración desde variables de entorno usando pydantic-settings, fallando rápidamente con un error explícito si faltan secretos requeridos como `JWT_SECRET`.

#### Escenario: Falta JWT_SECRET
- **CUANDO** la aplicación inicia sin `JWT_SECRET` configurado
- **ENTONCES** el sistema lanza un error de configuración explícito durante el inicio

#### Escenario: Configuración válida
- **CUANDO** todas las variables de entorno requeridas están provistas
- **ENTONCES** la instancia de Configuracion se carga correctamente con los valores del entorno o valores por defecto

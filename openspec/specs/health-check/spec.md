# Especificación: health-check

## Purpose

Provee un endpoint de verificación de vida para la API sin necesidad de conectividad a la base de datos, permitiendo monitorear la disponibilidad básica del servicio.

## Requirements

### Requirement: Endpoint de verificación de vida
El sistema SHALL exponer un endpoint `GET /health/live` que retorne HTTP 200 sin acceder a la base de datos.

#### Scenario: Verificación exitosa de vida
- **CUANDO** un cliente realiza una solicitud GET a `/health/live`
- **ENTONCES** el sistema retorna HTTP 200 con una respuesta exitosa

### Requirement: Inicialización de la aplicación
El sistema SHALL proveer una fábrica de aplicación FastAPI con logging estructurado y un contexto de ciclo de vida preparado para futuros hooks de inicialización.

#### Scenario: Creación de la aplicación
- **CUANDO** se llama a `create_app()`
- **ENTONCES** se retorna una instancia de FastAPI configurada con logging y ciclo de vida adjuntado

### Requirement: Carga de configuración
El sistema SHALL cargar la configuración desde variables de entorno usando pydantic-settings, fallando rápidamente con un error explícito si faltan secretos requeridos como `JWT_SECRET`.

#### Scenario: Falta JWT_SECRET
- **CUANDO** la aplicación inicia sin `JWT_SECRET` configurado
- **ENTONCES** el sistema lanza un error de configuración explícito durante el inicio

#### Scenario: Configuración válida
- **CUANDO** todas las variables de entorno requeridas están provistas
- **ENTONCES** la instancia de Configuracion se carga correctamente con los valores del entorno o valores por defecto

### Requirement: Endpoint de verificación de preparación (readiness probe)
El sistema SHALL exponer un endpoint `GET /health/ready` que verifique la conectividad activa a la base de datos PostgreSQL ejecutando una consulta `SELECT 1` con un tiempo de espera acotado.

#### Scenario: Verificación exitosa de base de datos
- **CUANDO** un cliente realiza una solicitud GET a `/health/ready` y la base de datos está disponible y responde dentro del tiempo límite
- **ENTONCES** el sistema retorna HTTP 200 con un cuerpo JSON `{"status": "ready"}`

#### Scenario: Base de datos inaccesible o timeout
- **CUANDO** un cliente realiza una solicitud GET a `/health/ready` y la base de datos no está disponible, rechaza la conexión o expira el tiempo de espera
- **ENTONCES** el sistema retorna HTTP 503 con código de estado `Service Unavailable`

# Spec Delta

## ADDED Requirements

### Requirement: Endpoint de verificación de preparación (readiness probe)
El sistema DEBE (SHALL) exponer un endpoint `GET /health/ready` que verifique la conectividad activa a la base de datos PostgreSQL ejecutando una consulta `SELECT 1` con un tiempo de espera acotado.

#### Scenario: Verificación exitosa de base de datos
- **CUANDO** un cliente realiza una solicitud GET a `/health/ready` y la base de datos está disponible y responde dentro del tiempo límite
- **ENTONCES** el sistema retorna HTTP 200 con un cuerpo JSON `{"status": "ready"}`

#### Scenario: Base de datos inaccesible o timeout
- **CUANDO** un cliente realiza una solicitud GET a `/health/ready` y la base de datos no está disponible, rechaza la conexión o expira el tiempo de espera
- **ENTONCES** el sistema retorna HTTP 503 con código de estado `Service Unavailable`

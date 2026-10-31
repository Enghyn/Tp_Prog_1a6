import uuid

import pytest

from tests.conftest import (
    cliente_http,
    crear_admin_prueba,
    crear_asignacion_prueba,
    crear_usuario_prueba,
    token_de_sesion,
)


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_smoke_flujo_completo(contexto_auth):
    sufijo = uuid.uuid4().hex[:8]
    email_cliente = f"smoke.{sufijo}@example.com"

    # 1. Auto-registro del cliente
    async with cliente_http() as c:
        r = await c.post("/auth/registro", json={
            "email": email_cliente,
            "nombre": "Cliente Smoke",
            "password": "Password123",
            "documento": f"DOC-SMOKE-{sufijo}",
            "telefono": "123",
        })
        assert r.status_code == 201
        cliente_id = r.json()["cliente_id"]

    # 2. Login del cliente (captura cookie access_token)
    async with cliente_http() as c:
        r = await c.post("/auth/login", json={"email": email_cliente, "password": "Password123"})
        assert r.status_code == 200
        assert "access_token" in c.cookies

    # Admin y mecanico
    admin, admin_token = await crear_admin_prueba(contexto_auth, email=f"admin.smoke.{sufijo}@example.com")
    mecanico = await crear_usuario_prueba(contexto_auth, f"mec.smoke.{sufijo}@example.com", password="Password123")
    await crear_asignacion_prueba(contexto_auth, mecanico.id, "MECANICO")
    await contexto_auth.flush()
    mecanico_token = token_de_sesion(mecanico.id, ["MECANICO"])

    # 3. Alta de vehiculo para el cliente registrado (admin)
    async with cliente_http(admin_token) as c:
        r = await c.post(f"/clientes/{cliente_id}/vehiculos", json={
            "patente": f"SMK-{sufijo[:6].upper()}",
            "marca": "Ford",
            "modelo": "Fiesta",
            "anio": 2020,
        })
        assert r.status_code == 201
        vehiculo_id = r.json()["id"]

        # Alta de repuesto
        r = await c.post("/repuestos", json={
            "codigo": f"REP-SMOKE-{sufijo}",
            "descripcion": "Repuesto smoke",
            "precio": "10.0",
            "stock": 5,
        })
        assert r.status_code == 201
        repuesto_id = r.json()["id"]

        # Apertura de orden
        r = await c.post("/ordenes", json={
            "vehiculo_id": vehiculo_id,
            "falla": "ruido",
            "items": [{"repuesto_id": repuesto_id, "cantidad": 2}],
        })
        assert r.status_code == 201
        orden_id = r.json()["id"]

    # 4. Iniciar (mecanico)
    async with cliente_http(mecanico_token) as c:
        r = await c.post(f"/ordenes/{orden_id}/iniciar")
        assert r.status_code == 200
        # 5. Terminar
        r = await c.post(f"/ordenes/{orden_id}/terminar")
        assert r.status_code == 200
        assert r.json()["estado"] == "TERMINADA"

    # 6. /mis-ordenes del cliente
    async with cliente_http() as c:
        lr = await c.post("/auth/login", json={"email": email_cliente, "password": "Password123"})
        assert lr.status_code == 200
        r = await c.get("/mis-ordenes?page=1&size=10")
        assert r.status_code == 200
        ordenes = r.json()["items"] if "items" in r.json() else r.json()
        assert any(o["id"] == orden_id for o in ordenes)

    # 7. /repuestos/{id}/movimientos
    async with cliente_http(admin_token) as c:
        r = await c.get(f"/repuestos/{repuesto_id}/movimientos")
        assert r.status_code == 200
        assert len(r.json()) >= 1

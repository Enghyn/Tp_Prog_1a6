import pytest
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import select, text

from tests.conftest import (
    cliente_http,
    crear_admin_prueba,
    crear_asignacion_prueba,
    crear_usuario_prueba,
    token_de_sesion,
)
from app.modules.clientes.models import Cliente, Vehiculo
from app.modules.ordenes.models import EstadoOrden, OrdenTrabajo
from app.modules.repuestos.models import Repuesto


async def _seed_estados(sesion):
    await sesion.execute(
        text(
            "INSERT INTO estado_orden (codigo, descripcion, posicion, es_final) VALUES "
            "('PENDIENTE','Pendiente',1,false),"
            "('EN_REPARACION','En reparacion',2,false),"
            "('TERMINADA','Terminada',3,true),"
            "('CANCELADA','Cancelada',4,true) "
            "ON CONFLICT (codigo) DO NOTHING"
        )
    )
    await sesion.flush()


async def _crear_cliente_usuario(sesion, email, documento, patente):
    usuario = await crear_usuario_prueba(sesion, email)
    await crear_asignacion_prueba(sesion, usuario.id, "CLIENTE")
    cliente = Cliente(nombre="Cliente", documento=documento, telefono="123", usuario_id=usuario.id)
    sesion.add(cliente)
    await sesion.flush()
    vehiculo = Vehiculo(cliente_id=cliente.id, patente=patente, marca="Ford", modelo="Fiesta", anio=2020)
    sesion.add(vehiculo)
    await sesion.flush()
    return usuario, cliente, vehiculo


async def _crear_repuesto(sesion, codigo="REP1", precio="10.00", stock=5):
    rep = Repuesto(codigo=codigo, descripcion="Repuesto", precio=Decimal(precio), stock=stock)
    sesion.add(rep)
    await sesion.flush()
    return rep


# ---------------------------------------------------------------------------
# Helpers para crear orden vía HTTP
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_orden_total_calculado_ignora_precio_enviado(contexto_auth):
    await _seed_estados(contexto_auth)
    admin, token = await crear_admin_prueba(contexto_auth)
    usuario, cliente, vehiculo = await _crear_cliente_usuario(
        contexto_auth, "cli1@taller.test", "DOC1", "PAT1"
    )
    rep = await _crear_repuesto(contexto_auth, codigo="R1", precio="10.00", stock=5)

    async with cliente_http(token) as c:
        r = await c.post(
            "/ordenes",
            json={
                "vehiculo_id": vehiculo.id,
                "falla": "ruido",
                "items": [{"repuesto_id": rep.id, "cantidad": 2}],
            },
        )
        assert r.status_code == 201, r.text
        data = r.json()
        assert Decimal(data["total"]) == Decimal("20.00")
        assert len(data["items"]) == 1
        assert Decimal(data["items"][0]["precio_unitario"]) == Decimal("10.00")
        assert data["items"][0]["cantidad"] == 2
        assert data["estado"] == "PENDIENTE"
        assert data["vehiculo"]["id"] == vehiculo.id


@pytest.mark.asyncio
async def test_post_orden_extra_field_precio_unitario_422(contexto_auth):
    await _seed_estados(contexto_auth)
    admin, token = await crear_admin_prueba(contexto_auth)
    usuario, cliente, vehiculo = await _crear_cliente_usuario(
        contexto_auth, "cli2@taller.test", "DOC2", "PAT2"
    )
    rep = await _crear_repuesto(contexto_auth, codigo="R2", precio="10.00", stock=5)

    async with cliente_http(token) as c:
        r = await c.post(
            "/ordenes",
            json={
                "vehiculo_id": vehiculo.id,
                "falla": "ruido",
                "items": [{"repuesto_id": rep.id, "cantidad": 1, "precio_unitario": "5.00"}],
            },
        )
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_post_orden_item_repetido_422(contexto_auth):
    await _seed_estados(contexto_auth)
    admin, token = await crear_admin_prueba(contexto_auth)
    usuario, cliente, vehiculo = await _crear_cliente_usuario(
        contexto_auth, "cli3@taller.test", "DOC3", "PAT3"
    )
    rep = await _crear_repuesto(contexto_auth, codigo="R3", precio="10.00", stock=5)

    async with cliente_http(token) as c:
        r = await c.post(
            "/ordenes",
            json={
                "vehiculo_id": vehiculo.id,
                "falla": "ruido",
                "items": [
                    {"repuesto_id": rep.id, "cantidad": 1},
                    {"repuesto_id": rep.id, "cantidad": 2},
                ],
            },
        )
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_post_orden_cantidad_cero_422(contexto_auth):
    await _seed_estados(contexto_auth)
    admin, token = await crear_admin_prueba(contexto_auth)
    usuario, cliente, vehiculo = await _crear_cliente_usuario(
        contexto_auth, "cli4@taller.test", "DOC4", "PAT4"
    )
    rep = await _crear_repuesto(contexto_auth, codigo="R4", precio="10.00", stock=5)

    async with cliente_http(token) as c:
        r = await c.post(
            "/ordenes",
            json={
                "vehiculo_id": vehiculo.id,
                "falla": "ruido",
                "items": [{"repuesto_id": rep.id, "cantidad": 0}],
            },
        )
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_post_orden_sin_items_422(contexto_auth):
    await _seed_estados(contexto_auth)
    admin, token = await crear_admin_prueba(contexto_auth)
    usuario, cliente, vehiculo = await _crear_cliente_usuario(
        contexto_auth, "cli5@taller.test", "DOC5", "PAT5"
    )

    async with cliente_http(token) as c:
        r = await c.post(
            "/ordenes",
            json={"vehiculo_id": vehiculo.id, "falla": "ruido", "items": []},
        )
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_post_orden_repuesto_dado_de_baja_409(contexto_auth):
    await _seed_estados(contexto_auth)
    admin, token = await crear_admin_prueba(contexto_auth)
    usuario, cliente, vehiculo = await _crear_cliente_usuario(
        contexto_auth, "cli6@taller.test", "DOC6", "PAT6"
    )
    rep = await _crear_repuesto(contexto_auth, codigo="R6", precio="10.00", stock=5)

    async with cliente_http(token) as c:
        await c.delete(f"/repuestos/{rep.id}")
        r = await c.post(
            "/ordenes",
            json={
                "vehiculo_id": vehiculo.id,
                "falla": "ruido",
                "items": [{"repuesto_id": rep.id, "cantidad": 1}],
            },
        )
        assert r.status_code == 409


@pytest.mark.asyncio
async def test_post_orden_repuesto_inexistente_404(contexto_auth):
    await _seed_estados(contexto_auth)
    admin, token = await crear_admin_prueba(contexto_auth)
    usuario, cliente, vehiculo = await _crear_cliente_usuario(
        contexto_auth, "cli7@taller.test", "DOC7", "PAT7"
    )

    async with cliente_http(token) as c:
        r = await c.post(
            "/ordenes",
            json={
                "vehiculo_id": vehiculo.id,
                "falla": "ruido",
                "items": [{"repuesto_id": 999999, "cantidad": 1}],
            },
        )
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_post_orden_catalogo_vacio_409(contexto_auth):
    from sqlalchemy import delete, text
    from app.modules.ordenes.models import EstadoOrden, OrdenTrabajo, ItemOrden, HistorialEstadoOrden
    from app.modules.repuestos.models import MovimientoStock
    await contexto_auth.execute(text("ALTER TABLE historial_estado_orden DISABLE TRIGGER ALL"))
    await contexto_auth.execute(text("ALTER TABLE movimiento_stock DISABLE TRIGGER ALL"))
    await contexto_auth.execute(delete(ItemOrden))
    await contexto_auth.execute(delete(HistorialEstadoOrden))
    await contexto_auth.execute(delete(MovimientoStock))
    await contexto_auth.execute(delete(OrdenTrabajo))
    await contexto_auth.execute(delete(EstadoOrden))
    await contexto_auth.flush()
    await contexto_auth.execute(text("ALTER TABLE historial_estado_orden ENABLE TRIGGER ALL"))
    await contexto_auth.execute(text("ALTER TABLE movimiento_stock ENABLE TRIGGER ALL"))
    # no seed estados
    admin, token = await crear_admin_prueba(contexto_auth)
    usuario, cliente, vehiculo = await _crear_cliente_usuario(
        contexto_auth, "cli8@taller.test", "DOC8", "PAT8"
    )
    rep = await _crear_repuesto(contexto_auth, codigo="R8", precio="10.00", stock=5)

    async with cliente_http(token) as c:
        r = await c.post(
            "/ordenes",
            json={
                "vehiculo_id": vehiculo.id,
                "falla": "ruido",
                "items": [{"repuesto_id": rep.id, "cantidad": 1}],
            },
        )
        assert r.status_code == 409


@pytest.mark.asyncio
async def test_post_orden_vehiculo_inexistente_404(contexto_auth):
    await _seed_estados(contexto_auth)
    admin, token = await crear_admin_prueba(contexto_auth)

    rep = await _crear_repuesto(contexto_auth, codigo="R9", precio="10.00", stock=5)

    async with cliente_http(token) as c:
        r = await c.post(
            "/ordenes",
            json={
                "vehiculo_id": 999999,
                "falla": "ruido",
                "items": [{"repuesto_id": rep.id, "cantidad": 1}],
            },
        )
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_post_orden_historial_desde_null(contexto_auth):
    await _seed_estados(contexto_auth)
    admin, token = await crear_admin_prueba(contexto_auth)
    usuario, cliente, vehiculo = await _crear_cliente_usuario(
        contexto_auth, "cli10@taller.test", "DOC10", "PAT10"
    )
    rep = await _crear_repuesto(contexto_auth, codigo="R10", precio="10.00", stock=5)

    async with cliente_http(token) as c:
        r = await c.post(
            "/ordenes",
            json={
                "vehiculo_id": vehiculo.id,
                "falla": "ruido",
                "items": [{"repuesto_id": rep.id, "cantidad": 1}],
            },
        )
        assert r.status_code == 201
        orden_id = r.json()["id"]

    # verificar historial
    from sqlalchemy import text as t

    res = await contexto_auth.execute(
        t("SELECT desde_estado, hasta_estado FROM historial_estado_orden WHERE orden_id = :oid"),
        {"oid": orden_id},
    )
    rows = res.fetchall()
    assert len(rows) == 1
    assert rows[0][0] is None
    assert rows[0][1] == "PENDIENTE"


# ---------------------------------------------------------------------------
# GET /ordenes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_ordenes_paginacion_y_filtro(contexto_auth):
    from sqlalchemy import delete, text
    from app.modules.ordenes.models import ItemOrden, OrdenTrabajo, HistorialEstadoOrden
    from app.modules.repuestos.models import MovimientoStock
    await contexto_auth.execute(text("ALTER TABLE historial_estado_orden DISABLE TRIGGER ALL"))
    await contexto_auth.execute(text("ALTER TABLE movimiento_stock DISABLE TRIGGER ALL"))
    await contexto_auth.execute(delete(ItemOrden))
    await contexto_auth.execute(delete(HistorialEstadoOrden))
    await contexto_auth.execute(delete(MovimientoStock))
    await contexto_auth.execute(delete(OrdenTrabajo))
    await contexto_auth.flush()
    await contexto_auth.execute(text("ALTER TABLE historial_estado_orden ENABLE TRIGGER ALL"))
    await contexto_auth.execute(text("ALTER TABLE movimiento_stock ENABLE TRIGGER ALL"))
    await _seed_estados(contexto_auth)
    admin, token = await crear_admin_prueba(contexto_auth)
    usuario, cliente, vehiculo = await _crear_cliente_usuario(
        contexto_auth, "cli11@taller.test", "DOC11", "PAT11"
    )
    rep = await _crear_repuesto(contexto_auth, codigo="R11", precio="10.00", stock=5)

    async with cliente_http(token) as c:
        for _ in range(3):
            await c.post(
                "/ordenes",
                json={
                    "vehiculo_id": vehiculo.id,
                    "falla": "ruido",
                    "items": [{"repuesto_id": rep.id, "cantidad": 1}],
                },
            )
        # paginacion
        r = await c.get("/ordenes", params={"page": 1, "size": 2})
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 3
        assert len(data["items"]) == 2
        assert data["pagina"] == 1
        assert data["tamanio"] == 2

        r2 = await c.get("/ordenes", params={"page": 2, "size": 2})
        assert r2.status_code == 200
        assert len(r2.json()["items"]) == 1

        # filtro por estado
        r3 = await c.get("/ordenes", params={"estado": "PENDIENTE"})
        assert r3.status_code == 200
        assert r3.json()["total"] == 3

        r4 = await c.get("/ordenes", params={"estado": "TERMINADA"})
        assert r4.status_code == 200
        assert r4.json()["total"] == 0


@pytest.mark.asyncio
async def test_get_ordenes_estado_invalido_422(contexto_auth):
    await _seed_estados(contexto_auth)
    admin, token = await crear_admin_prueba(contexto_auth)

    async with cliente_http(token) as c:
        r = await c.get("/ordenes", params={"estado": "NOPE"})
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# GET /ordenes/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_orden_404(contexto_auth):
    await _seed_estados(contexto_auth)
    admin, token = await crear_admin_prueba(contexto_auth)

    async with cliente_http(token) as c:
        r = await c.get("/ordenes/999999")
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_orden_200_precargados(contexto_auth):
    await _seed_estados(contexto_auth)
    admin, token = await crear_admin_prueba(contexto_auth)
    usuario, cliente, vehiculo = await _crear_cliente_usuario(
        contexto_auth, "cli12@taller.test", "DOC12", "PAT12"
    )
    rep = await _crear_repuesto(contexto_auth, codigo="R12", precio="10.00", stock=5)

    async with cliente_http(token) as c:
        r = await c.post(
            "/ordenes",
            json={
                "vehiculo_id": vehiculo.id,
                "falla": "ruido",
                "items": [{"repuesto_id": rep.id, "cantidad": 1}],
            },
        )
        oid = r.json()["id"]
        r2 = await c.get(f"/ordenes/{oid}")
        assert r2.status_code == 200
        data = r2.json()
        assert data["vehiculo"]["id"] == vehiculo.id
        assert data["items"][0]["repuesto"]["id"] == rep.id
        assert data["mecanico"] is None


@pytest.mark.asyncio
async def test_get_orden_403_no_corresponde(contexto_auth):
    await _seed_estados(contexto_auth)
    admin, token_admin = await crear_admin_prueba(contexto_auth)
    usuario, cliente, vehiculo = await _crear_cliente_usuario(
        contexto_auth, "cli13@taller.test", "DOC13", "PAT13"
    )
    rep = await _crear_repuesto(contexto_auth, codigo="R13", precio="10.00", stock=5)

    async with cliente_http(token_admin) as c:
        r = await c.post(
            "/ordenes",
            json={
                "vehiculo_id": vehiculo.id,
                "falla": "ruido",
                "items": [{"repuesto_id": rep.id, "cantidad": 1}],
            },
        )
        oid = r.json()["id"]

    # usuario sin roles
    norole = await crear_usuario_prueba(contexto_auth, "norole13@taller.test")
    token_norole = token_de_sesion(norole.id, [])
    async with cliente_http(token_norole) as c:
        r2 = await c.get(f"/ordenes/{oid}")
        assert r2.status_code == 403


# ---------------------------------------------------------------------------
# Ownership
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_duenio_ve_su_orden_y_ajeno_403(contexto_auth):
    await _seed_estados(contexto_auth)
    admin, token_admin = await crear_admin_prueba(contexto_auth)

    # cliente A
    userA, clienteA, vehA = await _crear_cliente_usuario(
        contexto_auth, "cliA@taller.test", "DOCA", "PATA"
    )
    # cliente B
    userB, clienteB, vehB = await _crear_cliente_usuario(
        contexto_auth, "cliB@taller.test", "DOCB", "PATB"
    )
    rep = await _crear_repuesto(contexto_auth, codigo="RAB", precio="10.00", stock=5)

    async with cliente_http(token_admin) as c:
        rA = await c.post(
            "/ordenes",
            json={
                "vehiculo_id": vehA.id,
                "falla": "ruido",
                "items": [{"repuesto_id": rep.id, "cantidad": 1}],
            },
        )
        oidA = rA.json()["id"]

    tokenA = token_de_sesion(userA.id, ["CLIENTE"])
    tokenB = token_de_sesion(userB.id, ["CLIENTE"])

    async with cliente_http(tokenA) as c:
        r = await c.get(f"/ordenes/{oidA}")
        assert r.status_code == 200

    async with cliente_http(tokenB) as c:
        r = await c.get(f"/ordenes/{oidA}")
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# GET /mis-ordenes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mis_ordenes_solo_del_cliente(contexto_auth):
    await _seed_estados(contexto_auth)
    admin, token_admin = await crear_admin_prueba(contexto_auth)

    userA, clienteA, vehA = await _crear_cliente_usuario(
        contexto_auth, "cliMA@taller.test", "DOCMA", "PATMA"
    )
    userB, clienteB, vehB = await _crear_cliente_usuario(
        contexto_auth, "cliMB@taller.test", "DOCMB", "PATMB"
    )
    rep = await _crear_repuesto(contexto_auth, codigo="RM", precio="10.00", stock=5)

    async with cliente_http(token_admin) as c:
        await c.post(
            "/ordenes",
            json={
                "vehiculo_id": vehA.id,
                "falla": "ruido",
                "items": [{"repuesto_id": rep.id, "cantidad": 1}],
            },
        )
        await c.post(
            "/ordenes",
            json={
                "vehiculo_id": vehB.id,
                "falla": "ruido",
                "items": [{"repuesto_id": rep.id, "cantidad": 1}],
            },
        )

    tokenA = token_de_sesion(userA.id, ["CLIENTE"])
    async with cliente_http(tokenA) as c:
        r = await c.get("/mis-ordenes")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["vehiculo"]["id"] == vehA.id


@pytest.mark.asyncio
async def test_mis_ordenes_sin_cliente_404(contexto_auth):
    await _seed_estados(contexto_auth)
    usuario = await crear_usuario_prueba(contexto_auth, "nocliente_ord@taller.test")
    await crear_asignacion_prueba(contexto_auth, usuario.id, "CLIENTE")
    token = token_de_sesion(usuario.id, ["CLIENTE"])

    async with cliente_http(token) as c:
        r = await c.get("/mis-ordenes")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /estados-orden
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_estados_orden_ordenados_por_posicion(contexto_auth):
    await _seed_estados(contexto_auth)
    admin, token = await crear_admin_prueba(contexto_auth)

    async with cliente_http(token) as c:
        r = await c.get("/estados-orden")
        assert r.status_code == 200
        data = r.json()
        posiciones = [e["posicion"] for e in data]
        assert posiciones == sorted(posiciones)
        codigos = [e["codigo"] for e in data]
        assert codigos == ["PENDIENTE", "EN_REPARACION", "TERMINADA", "CANCELADA"]


@pytest.mark.asyncio
async def test_estados_orden_sin_auth_401(contexto_auth):
    await _seed_estados(contexto_auth)
    async with cliente_http() as c:
        r = await c.get("/estados-orden")
        assert r.status_code == 401
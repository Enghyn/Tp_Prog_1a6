import pytest
from decimal import Decimal
from sqlalchemy import text

from tests.conftest import (
    cliente_http,
    crear_admin_prueba,
    crear_asignacion_prueba,
    crear_usuario_prueba,
    token_de_sesion,
)
from app.modules.clientes.models import Cliente, Vehiculo
from app.modules.ordenes.models import OrdenTrabajo
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


async def _crear_orden_http(client, vehiculo_id, rep_id, cantidad=1):
    r = await client.post(
        "/ordenes",
        json={
            "vehiculo_id": vehiculo_id,
            "falla": "ruido",
            "items": [{"repuesto_id": rep_id, "cantidad": cantidad}],
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ---------------------------------------------------------------------------
# iniciar
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_iniciar_asigna_mecanico(contexto_auth):
    await _seed_estados(contexto_auth)
    admin, token_admin = await crear_admin_prueba(contexto_auth)
    usuario, cliente, vehiculo = await _crear_cliente_usuario(
        contexto_auth, "cli_i1@taller.test", "DOCI1", "PATI1"
    )
    rep = await _crear_repuesto(contexto_auth, codigo="RI1", stock=5)

    async with cliente_http(token_admin) as c:
        oid = await _crear_orden_http(c, vehiculo.id, rep.id)

    mec = await crear_usuario_prueba(contexto_auth, "mec_i1@taller.test")
    await crear_asignacion_prueba(contexto_auth, mec.id, "MECANICO")
    token_mec = token_de_sesion(mec.id, ["MECANICO"])

    async with cliente_http(token_mec) as c:
        r = await c.post(f"/ordenes/{oid}/iniciar")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["estado"] == "EN_REPARACION"
        assert data["mecanico_id"] == mec.id

    res = await contexto_auth.execute(
        text("SELECT desde_estado, hasta_estado FROM historial_estado_orden WHERE orden_id = :oid"),
        {"oid": oid},
    )
    rows = res.fetchall()
    assert any(r[0] == "PENDIENTE" and r[1] == "EN_REPARACION" for r in rows)


@pytest.mark.asyncio
async def test_iniciar_conserva_mecanico(contexto_auth):
    await _seed_estados(contexto_auth)
    admin, token_admin = await crear_admin_prueba(contexto_auth)
    usuario, cliente, vehiculo = await _crear_cliente_usuario(
        contexto_auth, "cli_i2@taller.test", "DOCI2", "PATI2"
    )
    rep = await _crear_repuesto(contexto_auth, codigo="RI2", stock=5)

    async with cliente_http(token_admin) as c:
        oid = await _crear_orden_http(c, vehiculo.id, rep.id)

    mec_existente = await crear_usuario_prueba(contexto_auth, "mec_exist@taller.test")
    await crear_asignacion_prueba(contexto_auth, mec_existente.id, "MECANICO")
    # asignar mecánico preexistente directamente
    await contexto_auth.execute(
        text("UPDATE orden_trabajo SET mecanico_id = :m WHERE id = :oid"),
        {"m": mec_existente.id, "oid": oid},
    )
    await contexto_auth.flush()

    async with cliente_http(token_admin) as c:
        r = await c.post(f"/ordenes/{oid}/iniciar")
        assert r.status_code == 200, r.text
        assert r.json()["mecanico_id"] == mec_existente.id
        assert r.json()["estado"] == "EN_REPARACION"


@pytest.mark.asyncio
async def test_iniciar_transicion_invalida_409(contexto_auth):
    await _seed_estados(contexto_auth)
    admin, token_admin = await crear_admin_prueba(contexto_auth)
    usuario, cliente, vehiculo = await _crear_cliente_usuario(
        contexto_auth, "cli_i3@taller.test", "DOCI3", "PATI3"
    )
    rep = await _crear_repuesto(contexto_auth, codigo="RI3", stock=5)

    async with cliente_http(token_admin) as c:
        oid = await _crear_orden_http(c, vehiculo.id, rep.id)
        r1 = await c.post(f"/ordenes/{oid}/iniciar")
        assert r1.status_code == 200
        r2 = await c.post(f"/ordenes/{oid}/iniciar")
        assert r2.status_code == 409


@pytest.mark.asyncio
async def test_iniciar_inexistente_404(contexto_auth):
    await _seed_estados(contexto_auth)
    admin, token_admin = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token_admin) as c:
        r = await c.post("/ordenes/999999/iniciar")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# terminar
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_terminar_exito_descuenta_stock_y_movimiento(contexto_auth):
    await _seed_estados(contexto_auth)
    admin, token_admin = await crear_admin_prueba(contexto_auth)
    usuario, cliente, vehiculo = await _crear_cliente_usuario(
        contexto_auth, "cli_t1@taller.test", "DOCT1", "PATT1"
    )
    rep = await _crear_repuesto(contexto_auth, codigo="RT1", precio="10.00", stock=5)

    async with cliente_http(token_admin) as c:
        oid = await _crear_orden_http(c, vehiculo.id, rep.id, cantidad=2)
        r_init = await c.post(f"/ordenes/{oid}/iniciar")
        assert r_init.status_code == 200
        r_term = await c.post(f"/ordenes/{oid}/terminar")
        assert r_term.status_code == 200, r_term.text
        assert r_term.json()["estado"] == "TERMINADA"

        # stock descontado
        rg = await c.get(f"/repuestos/{rep.id}")
        assert rg.status_code == 200
        assert rg.json()["stock"] == 3

        # movimientos
        rm = await c.get(f"/repuestos/{rep.id}/movimientos")
        movs = rm.json()
        term_movs = [m for m in movs if m["motivo"] == "TERMINACION"]
        assert len(term_movs) == 1
        assert term_movs[0]["cantidad"] == -2
        assert term_movs[0]["orden_id"] == oid

    # historial
    res = await contexto_auth.execute(
        text("SELECT desde_estado, hasta_estado FROM historial_estado_orden WHERE orden_id = :oid"),
        {"oid": oid},
    )
    rows = res.fetchall()
    assert any(r[0] == "EN_REPARACION" and r[1] == "TERMINADA" for r in rows)


@pytest.mark.asyncio
async def test_terminar_stock_insuficiente_rollback(contexto_auth):
    await _seed_estados(contexto_auth)
    admin, token_admin = await crear_admin_prueba(contexto_auth)
    usuario, cliente, vehiculo = await _crear_cliente_usuario(
        contexto_auth, "cli_t2@taller.test", "DOCT2", "PATT2"
    )
    rep = await _crear_repuesto(contexto_auth, codigo="RT2", precio="10.00", stock=1)

    async with cliente_http(token_admin) as c:
        oid = await _crear_orden_http(c, vehiculo.id, rep.id, cantidad=2)
        await c.post(f"/ordenes/{oid}/iniciar")
        r_term = await c.post(f"/ordenes/{oid}/terminar")
        assert r_term.status_code == 409

        # stock intacto
        rg = await c.get(f"/repuestos/{rep.id}")
        assert rg.json()["stock"] == 1

        # estado intacto
        ro = await c.get(f"/ordenes/{oid}")
        assert ro.json()["estado"] == "EN_REPARACION"

    # sin movimiento de terminacion
    res = await contexto_auth.execute(
        text("SELECT count(*) FROM movimiento_stock WHERE orden_id = :oid AND motivo = 'TERMINACION'"),
        {"oid": oid},
    )
    assert res.scalar() == 0


@pytest.mark.asyncio
async def test_terminar_doble_409(contexto_auth):
    await _seed_estados(contexto_auth)
    admin, token_admin = await crear_admin_prueba(contexto_auth)
    usuario, cliente, vehiculo = await _crear_cliente_usuario(
        contexto_auth, "cli_t3@taller.test", "DOCT3", "PATT3"
    )
    rep = await _crear_repuesto(contexto_auth, codigo="RT3", precio="10.00", stock=5)

    async with cliente_http(token_admin) as c:
        oid = await _crear_orden_http(c, vehiculo.id, rep.id, cantidad=1)
        await c.post(f"/ordenes/{oid}/iniciar")
        r1 = await c.post(f"/ordenes/{oid}/terminar")
        assert r1.status_code == 200
        r2 = await c.post(f"/ordenes/{oid}/terminar")
        assert r2.status_code == 409


@pytest.mark.asyncio
async def test_terminar_no_en_reparacion_409(contexto_auth):
    await _seed_estados(contexto_auth)
    admin, token_admin = await crear_admin_prueba(contexto_auth)
    usuario, cliente, vehiculo = await _crear_cliente_usuario(
        contexto_auth, "cli_t4@taller.test", "DOCT4", "PATT4"
    )
    rep = await _crear_repuesto(contexto_auth, codigo="RT4", precio="10.00", stock=5)

    async with cliente_http(token_admin) as c:
        oid = await _crear_orden_http(c, vehiculo.id, rep.id, cantidad=1)
        # PENDIENTE -> terminar directo
        r = await c.post(f"/ordenes/{oid}/terminar")
        assert r.status_code == 409


@pytest.mark.asyncio
async def test_terminar_inexistente_404(contexto_auth):
    await _seed_estados(contexto_auth)
    admin, token_admin = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token_admin) as c:
        r = await c.post("/ordenes/999999/terminar")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# cancelar
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancelar_por_admin_200(contexto_auth):
    await _seed_estados(contexto_auth)
    admin, token_admin = await crear_admin_prueba(contexto_auth)
    usuario, cliente, vehiculo = await _crear_cliente_usuario(
        contexto_auth, "cli_c1@taller.test", "DOCC1", "PATC1"
    )
    rep = await _crear_repuesto(contexto_auth, codigo="RC1", stock=5)

    async with cliente_http(token_admin) as c:
        oid = await _crear_orden_http(c, vehiculo.id, rep.id)
        r = await c.post(f"/ordenes/{oid}/cancelar")
        assert r.status_code == 200, r.text
        assert r.json()["estado"] == "CANCELADA"

    res = await contexto_auth.execute(
        text("SELECT hasta_estado FROM historial_estado_orden WHERE orden_id = :oid"),
        {"oid": oid},
    )
    rows = [r[0] for r in res.fetchall()]
    assert "CANCELADA" in rows


@pytest.mark.asyncio
async def test_cancelar_por_duenio_200(contexto_auth):
    await _seed_estados(contexto_auth)
    admin, token_admin = await crear_admin_prueba(contexto_auth)
    usuario, cliente, vehiculo = await _crear_cliente_usuario(
        contexto_auth, "cli_c2@taller.test", "DOCC2", "PATC2"
    )
    rep = await _crear_repuesto(contexto_auth, codigo="RC2", stock=5)

    async with cliente_http(token_admin) as c:
        oid = await _crear_orden_http(c, vehiculo.id, rep.id)

    token_cliente = token_de_sesion(usuario.id, ["CLIENTE"])
    async with cliente_http(token_cliente) as c:
        r = await c.post(f"/ordenes/{oid}/cancelar")
        assert r.status_code == 200, r.text
        assert r.json()["estado"] == "CANCELADA"


@pytest.mark.asyncio
async def test_cancelar_ajena_403(contexto_auth):
    await _seed_estados(contexto_auth)
    admin, token_admin = await crear_admin_prueba(contexto_auth)
    usuario, cliente, vehiculo = await _crear_cliente_usuario(
        contexto_auth, "cli_c3@taller.test", "DOCC3", "PATC3"
    )
    rep = await _crear_repuesto(contexto_auth, codigo="RC3", stock=5)

    async with cliente_http(token_admin) as c:
        oid = await _crear_orden_http(c, vehiculo.id, rep.id)

    norole = await crear_usuario_prueba(contexto_auth, "norole_c3@taller.test")
    token_norole = token_de_sesion(norole.id, [])
    async with cliente_http(token_norole) as c:
        r = await c.post(f"/ordenes/{oid}/cancelar")
        assert r.status_code == 403


@pytest.mark.asyncio
async def test_cancelar_final_409(contexto_auth):
    await _seed_estados(contexto_auth)
    admin, token_admin = await crear_admin_prueba(contexto_auth)
    usuario, cliente, vehiculo = await _crear_cliente_usuario(
        contexto_auth, "cli_c4@taller.test", "DOCC4", "PATC4"
    )
    rep = await _crear_repuesto(contexto_auth, codigo="RC4", stock=5)

    async with cliente_http(token_admin) as c:
        oid = await _crear_orden_http(c, vehiculo.id, rep.id)
        await c.post(f"/ordenes/{oid}/iniciar")
        await c.post(f"/ordenes/{oid}/terminar")
        r = await c.post(f"/ordenes/{oid}/cancelar")
        assert r.status_code == 409


@pytest.mark.asyncio
async def test_cancelar_permisos_antes_estado_403(contexto_auth):
    await _seed_estados(contexto_auth)
    admin, token_admin = await crear_admin_prueba(contexto_auth)
    usuario, cliente, vehiculo = await _crear_cliente_usuario(
        contexto_auth, "cli_c5@taller.test", "DOCC5", "PATC5"
    )
    rep = await _crear_repuesto(contexto_auth, codigo="RC5", stock=5)

    async with cliente_http(token_admin) as c:
        oid = await _crear_orden_http(c, vehiculo.id, rep.id)
        await c.post(f"/ordenes/{oid}/iniciar")
        await c.post(f"/ordenes/{oid}/terminar")

    norole = await crear_usuario_prueba(contexto_auth, "norole_c5@taller.test")
    token_norole = token_de_sesion(norole.id, [])
    async with cliente_http(token_norole) as c:
        r = await c.post(f"/ordenes/{oid}/cancelar")
        assert r.status_code == 403


@pytest.mark.asyncio
async def test_cancelar_no_toca_stock(contexto_auth):
    await _seed_estados(contexto_auth)
    admin, token_admin = await crear_admin_prueba(contexto_auth)
    usuario, cliente, vehiculo = await _crear_cliente_usuario(
        contexto_auth, "cli_c6@taller.test", "DOCC6", "PATC6"
    )
    rep = await _crear_repuesto(contexto_auth, codigo="RC6", stock=5)

    async with cliente_http(token_admin) as c:
        oid = await _crear_orden_http(c, vehiculo.id, rep.id, cantidad=2)
        r0 = await c.get(f"/repuestos/{rep.id}")
        stock_antes = r0.json()["stock"]
        movs_antes = (await c.get(f"/repuestos/{rep.id}/movimientos")).json()
        n_antes = len(movs_antes)

        r = await c.post(f"/ordenes/{oid}/cancelar")
        assert r.status_code == 200

        r1 = await c.get(f"/repuestos/{rep.id}")
        assert r1.json()["stock"] == stock_antes
        movs_despues = (await c.get(f"/repuestos/{rep.id}/movimientos")).json()
        assert len(movs_despues) == n_antes


@pytest.mark.asyncio
async def test_cancelar_inexistente_404(contexto_auth):
    await _seed_estados(contexto_auth)
    admin, token_admin = await crear_admin_prueba(contexto_auth)
    async with cliente_http(token_admin) as c:
        r = await c.post("/ordenes/999999/cancelar")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# notificacion
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notificacion_agendada_solo_despues_commit(contexto_auth, monkeypatch):
    import app.modules.ordenes.router as router_mod

    class FakeNotifier:
        instances = []

        def __init__(self, background_tasks=None):
            self.background_tasks = background_tasks
            self.calls = []
            FakeNotifier.instances.append(self)

        def notificar_orden_terminada(self, orden_id, email=None, total=None):
            self.calls.append(
                {"orden_id": orden_id, "email": email, "total": total}
            )

    monkeypatch.setattr(router_mod, "BackgroundTasksNotifier", FakeNotifier)

    await _seed_estados(contexto_auth)
    admin, token_admin = await crear_admin_prueba(contexto_auth)
    usuario, cliente, vehiculo = await _crear_cliente_usuario(
        contexto_auth, "cli_n1@taller.test", "DOCN1", "PATN1"
    )
    rep = await _crear_repuesto(contexto_auth, codigo="RN1", stock=5)

    async with cliente_http(token_admin) as c:
        oid = await _crear_orden_http(c, vehiculo.id, rep.id, cantidad=1)
        await c.post(f"/ordenes/{oid}/iniciar")
        r = await c.post(f"/ordenes/{oid}/terminar")
        assert r.status_code == 200

    total_calls = sum(len(i.calls) for i in FakeNotifier.instances)
    assert total_calls == 1
    call = FakeNotifier.instances[-1].calls[0]
    assert call["orden_id"] == oid
    assert isinstance(call["orden_id"], int)
    assert isinstance(call["total"], float)
    # email resolved (user has usuario_id)
    # no session object
    for v in call.values():
        assert not hasattr(v, "execute")

    # failure case: stock insuficiente -> no call
    FakeNotifier.instances.clear()
    usuario2, cliente2, vehiculo2 = await _crear_cliente_usuario(
        contexto_auth, "cli_n2@taller.test", "DOCN2", "PATN2"
    )
    rep2 = await _crear_repuesto(contexto_auth, codigo="RN2", stock=1)
    async with cliente_http(token_admin) as c:
        oid2 = await _crear_orden_http(c, vehiculo2.id, rep2.id, cantidad=2)
        await c.post(f"/ordenes/{oid2}/iniciar")
        r2 = await c.post(f"/ordenes/{oid2}/terminar")
        assert r2.status_code == 409

    total_calls2 = sum(len(i.calls) for i in FakeNotifier.instances)
    assert total_calls2 == 0
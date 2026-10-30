"""Carga idempotente del estado inicial del taller mecánico.

Uso:
    python seed.py
    python seed.py --reset --si
    python seed.py --forzar          # solo si entorno=produccion

El script es la excepción documentada a la regla de commit exclusivo del
Unit of Work: no es un handler HTTP y administra su propia transacción.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from alembic import command
from alembic.config import Config as AlembicConfig

from app.core.configuracion import configuracion
from app.core.seguridad import hash_password_sync
from app.modules.clientes.models import Cliente, Vehiculo
from app.modules.ordenes.models import (
    EstadoOrden,
    HistorialEstadoOrden,
    ItemOrden,
    OrdenTrabajo,
)
from app.modules.repuestos.models import MovimientoStock, Repuesto
from app.modules.usuarios.models import AsignacionRol, EventoSeguridad, Usuario


logger = logging.getLogger("seed")


@dataclass(frozen=True)
class EstadoSeed:
    codigo: str
    descripcion: str
    posicion: int
    es_final: bool


ESTADOS_ORDEN: tuple[EstadoSeed, ...] = (
    EstadoSeed("PENDIENTE", "Pendiente de inicio", 1, False),
    EstadoSeed("EN_REPARACION", "En reparación", 2, False),
    EstadoSeed("TERMINADA", "Terminada", 3, True),
    EstadoSeed("CANCELADA", "Cancelada", 4, True),
)


@dataclass(frozen=True)
class UsuarioSeed:
    email: str
    nombre: str
    rol: str
    password: str
    debe_cambiar_password: bool


USUARIOS: tuple[UsuarioSeed, ...] = (
    UsuarioSeed(
        "admin@taller.local",
        "Administrador del Sistema",
        "ADMIN",
        "Admin123!",
        False,
    ),
    UsuarioSeed(
        "recepcion@taller.local",
        "Recepción del Taller",
        "RECEPCION",
        "Recepcion123!",
        False,
    ),
    UsuarioSeed(
        "mecanico@taller.local",
        "Mecánico del Taller",
        "MECANICO",
        "Mecanico123!",
        True,
    ),
    UsuarioSeed(
        "cliente@taller.local",
        "Cliente Demo",
        "CLIENTE",
        "Cliente123!",
        False,
    ),
)

CUANDO_INICIO = datetime(2026, 1, 2, 8, 0, tzinfo=timezone.utc)


@dataclass(frozen=True)
class RepuestoSeed:
    codigo: str
    descripcion: str
    precio: Decimal
    stock: int
    consumo_terminacion: int = 0


REPUESTOS: tuple[RepuestoSeed, ...] = (
    RepuestoSeed("FIL-001", "Filtro de aceite", Decimal("15000.00"), 10),
    RepuestoSeed("ACE-001", "Aceite sintético 5W-30", Decimal("12000.00"), 20),
    RepuestoSeed("BAT-001", "Batería 12V 60Ah", Decimal("85000.00"), 5, 1),
    RepuestoSeed("PAS-001", "Pastillas de freno delanteras", Decimal("45000.00"), 8),
)

CUANDO_ALTA = datetime(2026, 1, 2, 9, 0, tzinfo=timezone.utc)
CUANDO_EVENTO = datetime(2026, 1, 8, 0, 0, tzinfo=timezone.utc)


@dataclass(frozen=True)
class ClienteSeed:
    nombre: str
    documento: str
    telefono: str
    email_usuario: str | None


CLIENTES: tuple[ClienteSeed, ...] = (
    ClienteSeed("Cliente Demo Uno", "30111222", "1144440001", "cliente@taller.local"),
    ClienteSeed("Cliente Demo Dos", "30999888", "1144440002", None),
)


@dataclass(frozen=True)
class VehiculoSeed:
    patente: str
    marca: str
    modelo: str
    anio: int
    documento_cliente: str


VEHICULOS: tuple[VehiculoSeed, ...] = (
    VehiculoSeed("AB123CD", "Toyota", "Corolla", 2020, "30111222"),
    VehiculoSeed("AC456EF", "Ford", "Ranger", 2018, "30111222"),
    VehiculoSeed("AD789GH", "Volkswagen", "Gol", 2015, "30999888"),
)


@dataclass(frozen=True)
class ItemSeed:
    codigo_repuesto: str
    cantidad: int


@dataclass(frozen=True)
class TransicionSeed:
    desde: str | None
    hasta: str
    cuando: datetime


@dataclass(frozen=True)
class OrdenSeed:
    falla: str
    patente: str
    estado: str
    items: tuple[ItemSeed, ...]
    transiciones: tuple[TransicionSeed, ...]
    creada_en: datetime
    con_mecanico: bool
    repuesto_terminado: str | None = None


ORDENES: tuple[OrdenSeed, ...] = (
    OrdenSeed(
        "[demo] Ruido en tren delantero",
        "AB123CD",
        "PENDIENTE",
        (ItemSeed("PAS-001", 2),),
        (
            TransicionSeed(
                None, "PENDIENTE", datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc)
            ),
        ),
        datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc),
        False,
    ),
    OrdenSeed(
        "[demo] Service completo",
        "AC456EF",
        "EN_REPARACION",
        (ItemSeed("FIL-001", 1), ItemSeed("ACE-001", 2)),
        (
            TransicionSeed(
                None, "PENDIENTE", datetime(2026, 1, 6, 10, 0, tzinfo=timezone.utc)
            ),
            TransicionSeed(
                "PENDIENTE",
                "EN_REPARACION",
                datetime(2026, 1, 6, 11, 0, tzinfo=timezone.utc),
            ),
        ),
        datetime(2026, 1, 6, 10, 0, tzinfo=timezone.utc),
        True,
    ),
    OrdenSeed(
        "[demo] Batería agotada",
        "AD789GH",
        "TERMINADA",
        (ItemSeed("BAT-001", 1),),
        (
            TransicionSeed(
                None, "PENDIENTE", datetime(2026, 1, 7, 11, 0, tzinfo=timezone.utc)
            ),
            TransicionSeed(
                "PENDIENTE",
                "EN_REPARACION",
                datetime(2026, 1, 7, 12, 0, tzinfo=timezone.utc),
            ),
            TransicionSeed(
                "EN_REPARACION",
                "TERMINADA",
                datetime(2026, 1, 7, 15, 0, tzinfo=timezone.utc),
            ),
        ),
        datetime(2026, 1, 7, 11, 0, tzinfo=timezone.utc),
        True,
        "BAT-001",
    ),
)


_HASHES: dict[str, str] = {}


def _hash(contrasena: str) -> str:
    """Cachea el hash para no repetir bcrypt durante la misma ejecución."""
    if contrasena not in _HASHES:
        _HASHES[contrasena] = hash_password_sync(contrasena)
    return _HASHES[contrasena]



def _configurar_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


async def _cargar_estados(session: AsyncSession) -> dict[str, int]:
    creados = 0
    existentes = 0

    for esperado in ESTADOS_ORDEN:
        actual = (
            await session.execute(
                select(EstadoOrden).where(EstadoOrden.codigo == esperado.codigo)
            )
        ).scalar_one_or_none()

        if actual is None:
            session.add(
                EstadoOrden(
                    codigo=esperado.codigo,
                    descripcion=esperado.descripcion,
                    posicion=esperado.posicion,
                    es_final=esperado.es_final,
                )
            )
            creados += 1
            logger.info("estado_orden creado: %s", esperado.codigo)
            continue

        if (
            actual.descripcion != esperado.descripcion
            or actual.posicion != esperado.posicion
            or actual.es_final != esperado.es_final
        ):
            actual.descripcion = esperado.descripcion
            actual.posicion = esperado.posicion
            actual.es_final = esperado.es_final
            session.add(actual)
            logger.info("estado_orden actualizado: %s", esperado.codigo)
        else:
            existentes += 1
            logger.info("estado_orden existente: %s", esperado.codigo)

    await session.flush()
    return {"creados": creados, "existentes": existentes}


async def _cargar_usuarios(session: AsyncSession) -> dict[str, int]:
    creados = 0
    existentes = 0
    admin_id: int | None = None

    for esperado in USUARIOS:
        usuario = (
            await session.execute(
                select(Usuario).where(Usuario.email == esperado.email)
            )
        ).scalar_one_or_none()

        if usuario is None:
            usuario = Usuario(
                email=esperado.email,
                nombre=esperado.nombre,
                password_hash=_hash(esperado.password),
                activo=True,
                debe_cambiar_password=esperado.debe_cambiar_password,
                password_cambiada_en=None,
            )
            session.add(usuario)
            await session.flush()
            creados += 1
            logger.info("usuario creado: %s (%s)", esperado.email, esperado.rol)
        else:
            existentes += 1
            logger.info("usuario existente: %s", esperado.email)

        if esperado.rol == "ADMIN":
            admin_id = usuario.id

        abierta = (
            await session.execute(
                select(AsignacionRol).where(
                    AsignacionRol.usuario_id == usuario.id,
                    AsignacionRol.rol == esperado.rol,
                    AsignacionRol.revocada_en.is_(None),
                )
            )
        ).scalar_one_or_none()

        if abierta is None:
            session.add(
                AsignacionRol(
                    usuario_id=usuario.id,
                    rol=esperado.rol,
                    desde=CUANDO_INICIO,
                    vence_en=None,
                    revocada_en=None,
                    otorgada_por=None if esperado.rol == "ADMIN" else admin_id,
                )
            )
            logger.info("rol asignado: %s -> %s", esperado.rol, esperado.email)

    await session.flush()
    return {"creados": creados, "existentes": existentes}


async def _cargar_repuestos(session: AsyncSession) -> dict[str, int]:
    creados = 0
    existentes = 0

    admin = (
        await session.execute(
            select(Usuario).where(Usuario.email == "admin@taller.local")
        )
    ).scalar_one()

    for esperado in REPUESTOS:
        repuesto = (
            await session.execute(
                select(Repuesto).where(
                    Repuesto.codigo == esperado.codigo,
                    Repuesto.borrado_en.is_(None),
                )
            )
        ).scalar_one_or_none()

        if repuesto is not None:
            existentes += 1
            logger.info("repuesto existente: %s", esperado.codigo)
            continue

        repuesto = Repuesto(
            codigo=esperado.codigo,
            descripcion=esperado.descripcion,
            precio=esperado.precio,
            stock=esperado.stock,
            borrado_en=None,
        )
        session.add(repuesto)
        await session.flush()
        session.add(
            MovimientoStock(
                repuesto_id=repuesto.id,
                orden_id=None,
                usuario_id=admin.id,
                cantidad=esperado.stock + esperado.consumo_terminacion,
                motivo="ALTA",
                cuando=CUANDO_ALTA,
            )
        )
        creados += 1
        logger.info("repuesto creado: %s", esperado.codigo)

    await session.flush()
    return {"creados": creados, "existentes": existentes}


async def _cargar_clientes(session: AsyncSession) -> dict[str, int]:
    creados = 0
    existentes = 0

    emails = {esperado.email for esperado in USUARIOS if esperado.email}
    usuarios = (
        await session.execute(select(Usuario).where(Usuario.email.in_(emails)))
    ).scalars().all()
    usuarios_por_email = {usuario.email: usuario for usuario in usuarios}

    for esperado in CLIENTES:
        cliente = (
            await session.execute(
                select(Cliente).where(Cliente.documento == esperado.documento)
            )
        ).scalar_one_or_none()

        if cliente is not None:
            existentes += 1
            logger.info("cliente existente: %s", esperado.documento)
            continue

        usuario = (
            usuarios_por_email.get(esperado.email_usuario)
            if esperado.email_usuario is not None
            else None
        )
        session.add(
            Cliente(
                usuario_id=usuario.id if usuario is not None else None,
                nombre=esperado.nombre,
                documento=esperado.documento,
                telefono=esperado.telefono,
            )
        )
        creados += 1
        logger.info("cliente creado: %s", esperado.documento)

    await session.flush()
    return {"creados": creados, "existentes": existentes}


async def _cargar_vehiculos(session: AsyncSession) -> dict[str, int]:
    creados = 0
    existentes = 0

    clientes = (
        await session.execute(select(Cliente))
    ).scalars().all()
    clientes_por_documento = {
        cliente.documento: cliente for cliente in clientes
    }

    for esperado in VEHICULOS:
        vehiculo = (
            await session.execute(
                select(Vehiculo).where(
                    Vehiculo.patente == esperado.patente,
                    Vehiculo.borrado_en.is_(None),
                )
            )
        ).scalar_one_or_none()

        if vehiculo is not None:
            existentes += 1
            logger.info("vehiculo existente: %s", esperado.patente)
            continue

        cliente = clientes_por_documento[esperado.documento_cliente]
        session.add(
            Vehiculo(
                cliente_id=cliente.id,
                patente=esperado.patente,
                marca=esperado.marca,
                modelo=esperado.modelo,
                anio=esperado.anio,
                borrado_en=None,
            )
        )
        creados += 1
        logger.info("vehiculo creado: %s", esperado.patente)

    await session.flush()
    return {"creados": creados, "existentes": existentes}


def _buscar_historial(orden_id: int, transicion: TransicionSeed):
    consulta = select(HistorialEstadoOrden).where(
        HistorialEstadoOrden.orden_id == orden_id,
        HistorialEstadoOrden.hasta_estado == transicion.hasta,
        HistorialEstadoOrden.cuando == transicion.cuando,
    )
    if transicion.desde is None:
        consulta = consulta.where(HistorialEstadoOrden.desde_estado.is_(None))
    else:
        consulta = consulta.where(
            HistorialEstadoOrden.desde_estado == transicion.desde
        )
    return consulta


async def _cargar_ordenes(session: AsyncSession) -> dict[str, int]:
    creados = 0
    existentes = 0

    mecanico = (
        await session.execute(
            select(Usuario).where(Usuario.email == "mecanico@taller.local")
        )
    ).scalar_one()
    recepcion = (
        await session.execute(
            select(Usuario).where(Usuario.email == "recepcion@taller.local")
        )
    ).scalar_one()

    vehiculos = (
        await session.execute(
            select(Vehiculo).where(Vehiculo.borrado_en.is_(None))
        )
    ).scalars().all()
    vehiculos_por_patente = {vehiculo.patente: vehiculo for vehiculo in vehiculos}

    repuestos = (
        await session.execute(
            select(Repuesto).where(Repuesto.borrado_en.is_(None))
        )
    ).scalars().all()
    repuestos_por_codigo = {repuesto.codigo: repuesto for repuesto in repuestos}

    for esperado in ORDENES:
        vehiculo = vehiculos_por_patente[esperado.patente]
        orden = (
            await session.execute(
                select(OrdenTrabajo).where(
                    OrdenTrabajo.vehiculo_id == vehiculo.id,
                    OrdenTrabajo.falla == esperado.falla,
                )
            )
        ).scalar_one_or_none()

        if orden is None:
            total = sum(
                (
                    repuestos_por_codigo[item.codigo_repuesto].precio
                    * item.cantidad
                    for item in esperado.items
                ),
                Decimal("0.00"),
            )
            orden = OrdenTrabajo(
                vehiculo_id=vehiculo.id,
                mecanico_id=mecanico.id if esperado.con_mecanico else None,
                estado=esperado.estado,
                falla=esperado.falla,
                creada_en=esperado.creada_en,
                total=total,
            )
            session.add(orden)
            await session.flush()
            creados += 1
            logger.info("orden creada: %s", esperado.falla)
        else:
            existentes += 1
            logger.info("orden existente: %s", esperado.falla)

        for item in esperado.items:
            repuesto = repuestos_por_codigo[item.codigo_repuesto]
            existente = (
                await session.execute(
                    select(ItemOrden).where(
                        ItemOrden.orden_id == orden.id,
                        ItemOrden.repuesto_id == repuesto.id,
                    )
                )
            ).scalar_one_or_none()
            if existente is None:
                session.add(
                    ItemOrden(
                        orden_id=orden.id,
                        repuesto_id=repuesto.id,
                        cantidad=item.cantidad,
                        precio_unitario=repuesto.precio,
                    )
                )

        for transicion in esperado.transiciones:
            existente = (
                await session.execute(
                    _buscar_historial(orden.id, transicion)
                )
            ).scalar_one_or_none()
            if existente is None:
                usuario = (
                    recepcion if transicion.hasta == "PENDIENTE" else mecanico
                )
                session.add(
                    HistorialEstadoOrden(
                        orden_id=orden.id,
                        desde_estado=transicion.desde,
                        hasta_estado=transicion.hasta,
                        usuario_id=usuario.id,
                        cuando=transicion.cuando,
                    )
                )

        if esperado.repuesto_terminado is not None:
            repuesto = repuestos_por_codigo[esperado.repuesto_terminado]
            cuando = esperado.transiciones[-1].cuando
            existente = (
                await session.execute(
                    select(MovimientoStock).where(
                        MovimientoStock.repuesto_id == repuesto.id,
                        MovimientoStock.motivo == "TERMINACION",
                        MovimientoStock.cantidad == -1,
                        MovimientoStock.cuando == cuando,
                    )
                )
            ).scalar_one_or_none()
            if existente is None:
                session.add(
                    MovimientoStock(
                        repuesto_id=repuesto.id,
                        orden_id=orden.id,
                        usuario_id=mecanico.id,
                        cantidad=-1,
                        motivo="TERMINACION",
                        cuando=cuando,
                    )
                )

    await session.flush()
    return {"creados": creados, "existentes": existentes}


async def _cargar_evento(session: AsyncSession) -> dict[str, int]:
    existente = (
        await session.execute(
            select(EventoSeguridad).where(
                EventoSeguridad.actor == "SISTEMA",
                EventoSeguridad.accion == "seed_inicial",
            )
        )
    ).scalar_one_or_none()

    if existente is not None:
        logger.info("evento_seguridad existente: SISTEMA/seed_inicial")
        return {"creados": 0, "existentes": 1}

    session.add(
        EventoSeguridad(
            actor="SISTEMA",
            accion="seed_inicial",
            cuando=CUANDO_EVENTO,
        )
    )
    await session.flush()
    logger.info("evento_seguridad creado: SISTEMA/seed_inicial")
    return {"creados": 1, "existentes": 0}


async def ejecutar_seed(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, dict[str, int]]:
    """Ejecuta la carga inicial dentro de una única transacción."""
    resumen: dict[str, dict[str, int]] = {}

    async with session_factory() as session:
        async with session.begin():
            resumen["estado_orden"] = await _cargar_estados(session)
            resumen["usuario"] = await _cargar_usuarios(session)
            resumen["repuesto"] = await _cargar_repuestos(session)
            resumen["cliente"] = await _cargar_clientes(session)
            resumen["vehiculo"] = await _cargar_vehiculos(session)
            resumen["orden_trabajo"] = await _cargar_ordenes(session)
            resumen["evento_seguridad"] = await _cargar_evento(session)

    logger.info("seed finalizado: %s", resumen)
    return resumen


def _construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Carga idempotente del estado inicial del taller mecánico."
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Recrea el esquema con Alembic (downgrade base + upgrade head) antes de sembrar.",
    )
    parser.add_argument(
        "--si",
        action="store_true",
        help="Confirma explícitamente una operación destructiva (--reset).",
    )
    parser.add_argument(
        "--forzar",
        action="store_true",
        help="Permite ejecutar el seed con entorno=produccion.",
    )
    return parser


def _validar_guardias(args: argparse.Namespace) -> int | None:
    if configuracion.entorno.strip().lower() == "produccion" and not args.forzar:
        logger.error(
            "Seed abortado: entorno=produccion requiere --forzar de forma explícita."
        )
        return 2

    if args.reset and not args.si:
        logger.error(
            "Seed abortado: --reset es destructivo. Volvé a ejecutar con "
            "`python seed.py --reset --si` para confirmar."
        )
        return 2

    return None


def _reset_esquema() -> None:
    """Recrea el esquema con Alembic antes de sembrar.

    Se ejecuta fuera del event loop del seed: cada comando de Alembic abre y
    cierra su propio loop async. El reset dropea las tablas, por lo que no
    viola los triggers de solo-agregado (RN-15).
    """
    config = AlembicConfig("alembic.ini")
    logger.info("Reset solicitado: downgrade base")
    command.downgrade(config, "base")
    logger.info("Reset solicitado: upgrade head")
    command.upgrade(config, "head")


async def _ejecutar_con_engine() -> dict[str, dict[str, int]]:
    """Ejecuta el seed y libera el engine dentro del mismo event loop.

    asyncpg ata sus conexiones al loop que las creó; separar `dispose()` en un
    segundo `asyncio.run()` provoca `RuntimeError: Event loop is closed`.
    """
    engine = create_async_engine(configuracion.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    try:
        return await ejecutar_seed(session_factory)
    finally:
        await engine.dispose()


def main(argv: Sequence[str] | None = None) -> int:
    _configurar_logging()
    args = _construir_parser().parse_args(argv)

    guardia = _validar_guardias(args)
    if guardia is not None:
        return guardia

    if args.reset:
        try:
            _reset_esquema()
        except Exception:
            logger.exception("El reset del esquema falló; no se ejecutó el seed.")
            return 1

    try:
        asyncio.run(_ejecutar_con_engine())
    except Exception:
        logger.exception("Seed falló y la transacción fue revertida.")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

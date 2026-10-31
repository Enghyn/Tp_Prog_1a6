from datetime import datetime, timezone

import pytest
from sqlalchemy import DateTime, text
from sqlalchemy.types import TypeDecorator
from sqlmodel import SQLModel

from app.modules.usuarios.models import EventoSeguridad, Usuario


@pytest.mark.asyncio
async def test_todas_las_columnas_datetime_son_timezone_aware() -> None:
    infractoras: list[str] = []
    for tabla in SQLModel.metadata.tables.values():
        for columna in tabla.columns:
            tipo = columna.type
            if isinstance(tipo, TypeDecorator):
                tipo = tipo.impl
            if isinstance(tipo, DateTime) and tipo.timezone is not True:
                infractoras.append(f"{tabla.name}.{columna.name}")

    assert not infractoras, "Columnas DateTime naive: " + ", ".join(infractoras)
    temporales = {
        f"{tabla.name}.{columna.name}"
        for tabla in SQLModel.metadata.tables.values()
        for columna in tabla.columns
        if isinstance(
            columna.type.impl if isinstance(columna.type, TypeDecorator) else columna.type,
            DateTime,
        )
    }
    assert len(temporales) == 12
    assert "evento_seguridad.cuando" in temporales


@pytest.mark.asyncio
async def test_password_cambiada_en_roundtrip_preserva_instante_bajo_tz_no_utc(
    test_db_session,
) -> None:
    """Una zona no-UTC fuerza el corrimiento del esquema naive y prueba el fix."""
    original = datetime(2026, 10, 31, 1, 0, tzinfo=timezone.utc)
    await test_db_session.execute(text("SET TIME ZONE 'America/Buenos_Aires'"))
    usuario = Usuario(
        email="temporal-password@example.com",
        nombre="Temporal",
        password_hash="hash",
        password_cambiada_en=original,
    )
    test_db_session.add(usuario)
    await test_db_session.flush()
    await test_db_session.refresh(usuario)

    valor = usuario.password_cambiada_en
    assert valor is not None
    assert valor.tzinfo is not None
    assert valor.astimezone(timezone.utc) == original


@pytest.mark.asyncio
async def test_evento_seguridad_cuando_roundtrip_aware_utc(test_db_session) -> None:
    """La zona no-UTC hace determinista el desfase naive; el fix conserva el instante."""
    original = datetime(2026, 10, 31, 1, 0, 0, 123456, tzinfo=timezone.utc)
    await test_db_session.execute(text("SET TIME ZONE 'America/Buenos_Aires'"))
    evento = EventoSeguridad(
        cuando=original,
        actor="test@example.com",
        accion="TEST_TEMPORAL",
    )
    test_db_session.add(evento)
    await test_db_session.flush()
    await test_db_session.refresh(evento)

    valor = evento.cuando
    assert valor.tzinfo is not None
    assert valor.astimezone(timezone.utc) == original

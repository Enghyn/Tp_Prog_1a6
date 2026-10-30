from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.core.configuracion import configuracion


def crear_motor_bd(url: str | None = None) -> AsyncEngine:
    db_url = url or str(configuracion.database_url)
    return create_async_engine(db_url, pool_pre_ping=True)


def crear_fabricante_sesion(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


# Instancias globales a nivel de módulo (pueden ser reconfiguradas en lifespan)
engine: AsyncEngine = crear_motor_bd()
session_maker: async_sessionmaker[AsyncSession] = crear_fabricante_sesion(engine)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependencia de FastAPI para inyectar una sesión de base de datos por solicitud.
    Garantiza el cierre automático de la sesión mediante context manager.
    REGLA DURA: Esta dependencia NUNCA realiza commit(). El commit es responsabilidad
    exclusiva del Unit of Work.
    """
    async with session_maker() as session:
        yield session


# Alias en español para conveniencia
obtener_sesion = get_session

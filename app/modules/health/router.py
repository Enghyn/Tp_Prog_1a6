import asyncio
from typing import Annotated
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_session

router = APIRouter()


@router.get("/health/live")
async def estado_vivo():
    return {"estado": "ok"}


@router.get("/health/ready")
async def estado_preparado(session: Annotated[AsyncSession, Depends(get_session)]):
    try:
        await asyncio.wait_for(session.execute(text("SELECT 1")), timeout=2.0)
        return {"status": "ready"}
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"detail": "Base de datos no disponible", "codigo": "BASE_DE_DATOS_NO_DISPONIBLE"},
        )

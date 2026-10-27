from fastapi import APIRouter

router = APIRouter()


@router.get("/health/live")
async def estado_vivo():
    return {"estado": "ok"}

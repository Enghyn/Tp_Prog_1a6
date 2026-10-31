from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class RepuestoCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codigo: str = Field(min_length=1, max_length=60)
    descripcion: str = Field(min_length=1, max_length=200)
    precio: Decimal = Field(gt=0)
    stock: int = Field(default=0, ge=0)


class RepuestoUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    descripcion: str | None = Field(default=None, min_length=1, max_length=200)
    precio: Decimal | None = Field(default=None, gt=0)


class RepuestoRead(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    codigo: str
    descripcion: str
    precio: Decimal
    stock: int


class MovimientoStockRead(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    repuesto_id: int
    orden_id: int | None = None
    usuario_id: int
    cantidad: int
    motivo: str
    cuando: datetime


class HistorialPrecioRead(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    repuesto_id: int
    usuario_id: int
    precio_anterior: Decimal
    precio_nuevo: Decimal
    cuando: datetime


class ReponerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cantidad: int = Field(gt=0)

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.clientes.schemas import VehiculoRead
from app.modules.repuestos.schemas import RepuestoRead


class UsuarioRead(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    email: str
    nombre: str


class ItemOrdenCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repuesto_id: int
    cantidad: int = Field(gt=0)


class OrdenCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vehiculo_id: int
    falla: str = Field(min_length=1)
    items: list[ItemOrdenCreate] = Field(min_length=1)


class ItemOrdenRead(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    repuesto_id: int
    cantidad: int
    precio_unitario: Decimal
    repuesto: RepuestoRead


class OrdenRead(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    vehiculo_id: int
    mecanico_id: int | None
    estado: str
    falla: str
    creada_en: datetime
    total: Decimal
    vehiculo: VehiculoRead
    items: list[ItemOrdenRead]
    mecanico: UsuarioRead | None


class EstadoOrdenRead(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    codigo: str
    descripcion: str
    posicion: int
    es_final: bool
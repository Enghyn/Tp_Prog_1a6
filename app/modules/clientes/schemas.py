from pydantic import BaseModel, ConfigDict, Field


class ClienteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: str = Field(min_length=1, max_length=120)
    documento: str = Field(min_length=1, max_length=40)
    telefono: str = Field(min_length=1, max_length=40)


class VehiculoCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patente: str = Field(min_length=1, max_length=20)
    marca: str = Field(min_length=1, max_length=60)
    modelo: str = Field(min_length=1, max_length=60)
    anio: int = Field(ge=1950, le=2100)


class VehiculoRead(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    cliente_id: int
    patente: str
    marca: str
    modelo: str
    anio: int


class ClienteRead(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    usuario_id: int | None
    nombre: str
    documento: str
    telefono: str
    vehiculos: list[VehiculoRead] = []
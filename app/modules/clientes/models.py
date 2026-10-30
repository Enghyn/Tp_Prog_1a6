from datetime import datetime
from typing import List, Optional

from sqlalchemy import CheckConstraint, DateTime, Index, text
from sqlmodel import Field, Relationship, SQLModel


class Cliente(SQLModel, table=True):
    __tablename__ = "cliente"

    id: Optional[int] = Field(default=None, primary_key=True)
    usuario_id: Optional[int] = Field(default=None, foreign_key="usuario.id", nullable=True)
    nombre: str = Field(nullable=False)
    documento: str = Field(nullable=False)
    telefono: str = Field(nullable=False)

    vehiculos: List["Vehiculo"] = Relationship(
        back_populates="cliente",
        sa_relationship_kwargs={"lazy": "raise"},
    )

    __table_args__ = (
        Index("uq_cliente_documento", "documento", unique=True),
        Index("uq_cliente_usuario", "usuario_id", unique=True, postgresql_where=text("usuario_id IS NOT NULL")),
    )


class Vehiculo(SQLModel, table=True):
    __tablename__ = "vehiculo"

    id: Optional[int] = Field(default=None, primary_key=True)
    cliente_id: int = Field(foreign_key="cliente.id", nullable=False)
    patente: str = Field(nullable=False)
    marca: str = Field(nullable=False)
    modelo: str = Field(nullable=False)
    anio: int = Field(nullable=False)
    borrado_en: Optional[datetime] = Field(
        default=None, nullable=True, sa_type=DateTime(timezone=True)
    )

    cliente: Optional[Cliente] = Relationship(
        back_populates="vehiculos",
        sa_relationship_kwargs={"lazy": "raise"},
    )

    __table_args__ = (
        CheckConstraint("anio >= 1950 AND anio <= 2100", name="ck_vehiculo_anio"),
        Index(
            "uq_vehiculo_patente_vigente",
            "patente",
            unique=True,
            postgresql_where=text("borrado_en IS NULL"),
        ),
    )

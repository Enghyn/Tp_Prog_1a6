from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import CheckConstraint, DateTime, Index, Numeric, text
from sqlmodel import Field, Relationship, SQLModel


class Repuesto(SQLModel, table=True):
    __tablename__ = "repuesto"

    id: Optional[int] = Field(default=None, primary_key=True)
    codigo: str = Field(nullable=False)
    descripcion: str = Field(nullable=False)
    precio: Decimal = Field(sa_type=Numeric(10, 2), nullable=False)
    stock: int = Field(nullable=False, default=0)
    borrado_en: Optional[datetime] = Field(
        default=None, nullable=True, sa_type=DateTime(timezone=True)
    )

    movimientos: List["MovimientoStock"] = Relationship(
        back_populates="repuesto",
        sa_relationship_kwargs={"lazy": "raise"},
    )
    historial_precios: List["HistorialPrecioRepuesto"] = Relationship(
        back_populates="repuesto",
        sa_relationship_kwargs={"lazy": "raise"},
    )

    __table_args__ = (
        CheckConstraint("precio > 0", name="ck_repuesto_precio_positivo"),
        CheckConstraint("stock >= 0", name="ck_repuesto_stock_no_negativo"),
        Index(
            "uq_repuesto_codigo_vigente",
            "codigo",
            unique=True,
            postgresql_where=text("borrado_en IS NULL"),
        ),
    )


class MovimientoStock(SQLModel, table=True):
    __tablename__ = "movimiento_stock"

    id: Optional[int] = Field(default=None, primary_key=True)
    repuesto_id: int = Field(foreign_key="repuesto.id", nullable=False)
    orden_id: Optional[int] = Field(default=None, foreign_key="orden_trabajo.id", nullable=True)
    usuario_id: int = Field(foreign_key="usuario.id", nullable=False)
    cantidad: int = Field(nullable=False)
    motivo: str = Field(nullable=False)
    cuando: datetime = Field(nullable=False, sa_type=DateTime(timezone=True))

    repuesto: Optional[Repuesto] = Relationship(
        back_populates="movimientos",
        sa_relationship_kwargs={"lazy": "raise"},
    )

    __table_args__ = (
        CheckConstraint("cantidad != 0", name="ck_movimiento_cantidad_no_nula"),
    )


class HistorialPrecioRepuesto(SQLModel, table=True):
    __tablename__ = "historial_precio_repuesto"

    id: Optional[int] = Field(default=None, primary_key=True)
    repuesto_id: int = Field(foreign_key="repuesto.id", nullable=False)
    usuario_id: int = Field(foreign_key="usuario.id", nullable=False)
    precio_anterior: Decimal = Field(sa_type=Numeric(10, 2), nullable=False)
    precio_nuevo: Decimal = Field(sa_type=Numeric(10, 2), nullable=False)
    cuando: datetime = Field(nullable=False, sa_type=DateTime(timezone=True))

    repuesto: Optional[Repuesto] = Relationship(
        back_populates="historial_precios",
        sa_relationship_kwargs={"lazy": "raise"},
    )

    __table_args__ = (
        CheckConstraint("precio_nuevo > 0", name="ck_hpr_precio_nuevo_positivo"),
        CheckConstraint("precio_nuevo > precio_anterior", name="ck_hpr_precio_nuevo_mayor"),
    )

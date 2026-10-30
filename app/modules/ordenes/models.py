from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import CheckConstraint, DateTime, Index, Numeric, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


class EstadoOrden(SQLModel, table=True):
    __tablename__ = "estado_orden"

    codigo: str = Field(primary_key=True)
    descripcion: str = Field(nullable=False)
    posicion: int = Field(nullable=False)
    es_final: bool = Field(default=False, nullable=False)

    ordenes: List["OrdenTrabajo"] = Relationship(
        back_populates="estado_ref",
        sa_relationship_kwargs={"lazy": "raise", "foreign_keys": "[OrdenTrabajo.estado]"},
    )
    historial_desde: List["HistorialEstadoOrden"] = Relationship(
        back_populates="desde_estado_ref",
        sa_relationship_kwargs={"lazy": "raise", "foreign_keys": "[HistorialEstadoOrden.desde_estado]"},
    )
    historial_hasta: List["HistorialEstadoOrden"] = Relationship(
        back_populates="hasta_estado_ref",
        sa_relationship_kwargs={"lazy": "raise", "foreign_keys": "[HistorialEstadoOrden.hasta_estado]"},
    )

    __table_args__ = (
        Index("uq_estado_orden_posicion", "posicion", unique=True),
    )


class OrdenTrabajo(SQLModel, table=True):
    __tablename__ = "orden_trabajo"

    id: Optional[int] = Field(default=None, primary_key=True)
    vehiculo_id: int = Field(foreign_key="vehiculo.id", nullable=False)
    mecanico_id: Optional[int] = Field(default=None, foreign_key="usuario.id", nullable=True)
    estado: str = Field(foreign_key="estado_orden.codigo", nullable=False)
    falla: str = Field(nullable=False)
    creada_en: datetime = Field(nullable=False, sa_type=DateTime(timezone=True))
    total: Decimal = Field(
        sa_type=Numeric(12, 2),
        default=Decimal("0"),
        nullable=False,
    )

    estado_ref: Optional[EstadoOrden] = Relationship(
        back_populates="ordenes",
        sa_relationship_kwargs={"lazy": "raise", "foreign_keys": "[OrdenTrabajo.estado]"},
    )
    items: List["ItemOrden"] = Relationship(
        back_populates="orden",
        sa_relationship_kwargs={
            "lazy": "raise",
            "cascade": "all, delete-orphan",
        },
    )
    historial_estados: List["HistorialEstadoOrden"] = Relationship(
        back_populates="orden",
        sa_relationship_kwargs={"lazy": "raise"},
    )

    __table_args__ = (
        CheckConstraint("total >= 0", name="ck_orden_total_no_negativo"),
    )


class ItemOrden(SQLModel, table=True):
    __tablename__ = "item_orden"

    id: Optional[int] = Field(default=None, primary_key=True)
    orden_id: int = Field(foreign_key="orden_trabajo.id", nullable=False)
    repuesto_id: int = Field(foreign_key="repuesto.id", nullable=False)
    cantidad: int = Field(nullable=False)
    precio_unitario: Decimal = Field(sa_type=Numeric(10, 2), nullable=False)

    orden: Optional[OrdenTrabajo] = Relationship(
        back_populates="items",
        sa_relationship_kwargs={"lazy": "raise"},
    )

    __table_args__ = (
        UniqueConstraint("orden_id", "repuesto_id", name="uq_item_orden_repuesto"),
        CheckConstraint("cantidad > 0", name="ck_item_cantidad_positiva"),
        CheckConstraint("precio_unitario > 0", name="ck_item_precio_positivo"),
    )


class HistorialEstadoOrden(SQLModel, table=True):
    __tablename__ = "historial_estado_orden"

    id: Optional[int] = Field(default=None, primary_key=True)
    orden_id: int = Field(foreign_key="orden_trabajo.id", nullable=False)
    desde_estado: Optional[str] = Field(default=None, foreign_key="estado_orden.codigo", nullable=True)
    hasta_estado: str = Field(foreign_key="estado_orden.codigo", nullable=False)
    usuario_id: int = Field(foreign_key="usuario.id", nullable=False)
    cuando: datetime = Field(nullable=False, sa_type=DateTime(timezone=True))

    orden: Optional[OrdenTrabajo] = Relationship(
        back_populates="historial_estados",
        sa_relationship_kwargs={"lazy": "raise"},
    )
    desde_estado_ref: Optional[EstadoOrden] = Relationship(
        back_populates="historial_desde",
        sa_relationship_kwargs={"lazy": "raise", "foreign_keys": "[HistorialEstadoOrden.desde_estado]"},
    )
    hasta_estado_ref: Optional[EstadoOrden] = Relationship(
        back_populates="historial_hasta",
        sa_relationship_kwargs={"lazy": "raise", "foreign_keys": "[HistorialEstadoOrden.hasta_estado]"},
    )

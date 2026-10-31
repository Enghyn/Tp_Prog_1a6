from datetime import datetime
from typing import List, Optional

from sqlalchemy import CheckConstraint, DateTime, Index, UniqueConstraint, text, func
from sqlmodel import Field, Relationship, SQLModel


ROLES_VALIDOS = ("ADMIN", "RECEPCION", "MECANICO", "CLIENTE")


class Usuario(SQLModel, table=True):
    __tablename__ = "usuario"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, nullable=False)
    nombre: str = Field(nullable=False)
    password_hash: str = Field(nullable=False)
    activo: bool = Field(default=True, nullable=False)
    debe_cambiar_password: bool = Field(default=False, nullable=False)
    password_cambiada_en: Optional[datetime] = Field(
        default=None, nullable=True, sa_type=DateTime(timezone=True)
    )

    asignaciones: List["AsignacionRol"] = Relationship(
        back_populates="usuario",
        sa_relationship_kwargs={
            "lazy": "raise",
            "foreign_keys": "[AsignacionRol.usuario_id]",
        },
    )


class AsignacionRol(SQLModel, table=True):
    __tablename__ = "asignacion_rol"

    id: Optional[int] = Field(default=None, primary_key=True)
    usuario_id: int = Field(foreign_key="usuario.id", nullable=False)
    rol: str = Field(nullable=False)
    desde: datetime = Field(nullable=False, sa_type=DateTime(timezone=True))
    vence_en: Optional[datetime] = Field(
        default=None, nullable=True, sa_type=DateTime(timezone=True)
    )
    revocada_en: Optional[datetime] = Field(
        default=None, nullable=True, sa_type=DateTime(timezone=True)
    )
    otorgada_por: Optional[int] = Field(default=None, foreign_key="usuario.id", nullable=True)

    usuario: Optional[Usuario] = Relationship(
        back_populates="asignaciones",
        sa_relationship_kwargs={"lazy": "raise", "foreign_keys": "[AsignacionRol.usuario_id]"},
    )
    otorgado_por_usuario: Optional[Usuario] = Relationship(
        sa_relationship_kwargs={"lazy": "raise", "foreign_keys": "[AsignacionRol.otorgada_por]"},
    )

    __table_args__ = (
        CheckConstraint(
            "rol IN ('ADMIN', 'RECEPCION', 'MECANICO', 'CLIENTE')",
            name="ck_asignacion_rol_valido",
        ),
        Index(
            "uq_asignacion_rol_abierta",
            "usuario_id",
            "rol",
            unique=True,
            postgresql_where=text("revocada_en IS NULL"),
        ),
    )


class IntentoAcceso(SQLModel, table=True):
    __tablename__ = "intento_acceso"

    id: Optional[int] = Field(default=None, primary_key=True)
    cuando: datetime = Field(nullable=False, sa_type=DateTime(timezone=True))
    email: str = Field(nullable=False)
    ip: str = Field(nullable=False)
    exito: bool = Field(nullable=False)

    __table_args__ = (
        Index("ix_intento_acceso_email_ip_cuando", "email", "ip", "cuando"),
    )


class EventoSeguridad(SQLModel, table=True):
    __tablename__ = "evento_seguridad"

    id: Optional[int] = Field(default=None, primary_key=True)
    cuando: datetime = Field(
        nullable=False,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={"server_default": func.now()},
    )
    actor: str = Field(nullable=False)
    accion: str = Field(nullable=False)

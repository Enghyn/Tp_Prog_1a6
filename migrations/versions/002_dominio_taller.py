"""002_dominio_taller

Revision ID: 002_dominio_taller
Revises: 001_auth_core
Create Date: 2026-10-30 13:00:00.000000

Tablas del dominio del taller mecánico:
  cliente, vehiculo, repuesto, estado_orden, orden_trabajo, item_orden,
  historial_estado_orden, movimiento_stock, historial_precio_repuesto

Incluye FKs, CHECKs e índices únicos parciales para borrado lógico.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "002_dominio_taller"
down_revision: Union[str, None] = "001_auth_core"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # cliente
    # ------------------------------------------------------------------
    op.create_table(
        "cliente",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("nombre", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("documento", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("telefono", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_cliente_documento", "cliente", ["documento"], unique=True)
    op.create_index(
        "uq_cliente_usuario",
        "cliente",
        ["usuario_id"],
        unique=True,
        postgresql_where=sa.text("usuario_id IS NOT NULL"),
    )

    # ------------------------------------------------------------------
    # vehiculo
    # ------------------------------------------------------------------
    op.create_table(
        "vehiculo",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cliente_id", sa.Integer(), nullable=False),
        sa.Column("patente", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("marca", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("modelo", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("anio", sa.Integer(), nullable=False),
        sa.Column("borrado_en", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("anio >= 1950 AND anio <= 2100", name="ck_vehiculo_anio"),
        sa.ForeignKeyConstraint(["cliente_id"], ["cliente.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_vehiculo_patente_vigente",
        "vehiculo",
        ["patente"],
        unique=True,
        postgresql_where=sa.text("borrado_en IS NULL"),
    )

    # ------------------------------------------------------------------
    # repuesto
    # ------------------------------------------------------------------
    op.create_table(
        "repuesto",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("codigo", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("descripcion", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("precio", sa.Numeric(10, 2), nullable=False),
        sa.Column("stock", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("borrado_en", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("precio > 0", name="ck_repuesto_precio_positivo"),
        sa.CheckConstraint("stock >= 0", name="ck_repuesto_stock_no_negativo"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_repuesto_codigo_vigente",
        "repuesto",
        ["codigo"],
        unique=True,
        postgresql_where=sa.text("borrado_en IS NULL"),
    )

    # ------------------------------------------------------------------
    # estado_orden (catálogo)
    # ------------------------------------------------------------------
    op.create_table(
        "estado_orden",
        sa.Column("codigo", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("descripcion", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("posicion", sa.Integer(), nullable=False),
        sa.Column("es_final", sa.Boolean(), nullable=False, server_default="false"),
        sa.PrimaryKeyConstraint("codigo"),
    )
    op.create_index("uq_estado_orden_posicion", "estado_orden", ["posicion"], unique=True)

    # ------------------------------------------------------------------
    # orden_trabajo
    # ------------------------------------------------------------------
    op.create_table(
        "orden_trabajo",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("vehiculo_id", sa.Integer(), nullable=False),
        sa.Column("mecanico_id", sa.Integer(), nullable=True),
        sa.Column("estado", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("falla", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("creada_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.CheckConstraint("total >= 0", name="ck_orden_total_no_negativo"),
        sa.ForeignKeyConstraint(["vehiculo_id"], ["vehiculo.id"]),
        sa.ForeignKeyConstraint(["mecanico_id"], ["usuario.id"]),
        sa.ForeignKeyConstraint(["estado"], ["estado_orden.codigo"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # ------------------------------------------------------------------
    # item_orden
    # ------------------------------------------------------------------
    op.create_table(
        "item_orden",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("orden_id", sa.Integer(), nullable=False),
        sa.Column("repuesto_id", sa.Integer(), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("precio_unitario", sa.Numeric(10, 2), nullable=False),
        sa.CheckConstraint("cantidad > 0", name="ck_item_cantidad_positiva"),
        sa.CheckConstraint("precio_unitario > 0", name="ck_item_precio_positivo"),
        sa.UniqueConstraint("orden_id", "repuesto_id", name="uq_item_orden_repuesto"),
        sa.ForeignKeyConstraint(["orden_id"], ["orden_trabajo.id"]),
        sa.ForeignKeyConstraint(["repuesto_id"], ["repuesto.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # ------------------------------------------------------------------
    # historial_estado_orden (solo-agregado — protegida por trigger en 003)
    # ------------------------------------------------------------------
    op.create_table(
        "historial_estado_orden",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("orden_id", sa.Integer(), nullable=False),
        sa.Column("desde_estado", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("hasta_estado", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("cuando", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["orden_id"], ["orden_trabajo.id"]),
        sa.ForeignKeyConstraint(["desde_estado"], ["estado_orden.codigo"]),
        sa.ForeignKeyConstraint(["hasta_estado"], ["estado_orden.codigo"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # ------------------------------------------------------------------
    # movimiento_stock (solo-agregado — protegida por trigger en 003)
    # ------------------------------------------------------------------
    op.create_table(
        "movimiento_stock",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("repuesto_id", sa.Integer(), nullable=False),
        sa.Column("orden_id", sa.Integer(), nullable=True),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("motivo", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("cuando", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("cantidad != 0", name="ck_movimiento_cantidad_no_nula"),
        sa.ForeignKeyConstraint(["repuesto_id"], ["repuesto.id"]),
        sa.ForeignKeyConstraint(["orden_id"], ["orden_trabajo.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # ------------------------------------------------------------------
    # historial_precio_repuesto (solo-agregado — protegida por trigger en 003)
    # ------------------------------------------------------------------
    op.create_table(
        "historial_precio_repuesto",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("repuesto_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("precio_anterior", sa.Numeric(10, 2), nullable=False),
        sa.Column("precio_nuevo", sa.Numeric(10, 2), nullable=False),
        sa.Column("cuando", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("precio_nuevo > 0", name="ck_hpr_precio_nuevo_positivo"),
        sa.CheckConstraint("precio_nuevo > precio_anterior", name="ck_hpr_precio_nuevo_mayor"),
        sa.ForeignKeyConstraint(["repuesto_id"], ["repuesto.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("historial_precio_repuesto")
    op.drop_table("movimiento_stock")
    op.drop_table("historial_estado_orden")
    op.drop_table("item_orden")
    op.drop_table("orden_trabajo")
    op.drop_index("uq_estado_orden_posicion", table_name="estado_orden")
    op.drop_table("estado_orden")
    op.drop_index("uq_repuesto_codigo_vigente", table_name="repuesto")
    op.drop_table("repuesto")
    op.drop_index("uq_vehiculo_patente_vigente", table_name="vehiculo")
    op.drop_table("vehiculo")
    op.drop_index("uq_cliente_usuario", table_name="cliente")
    op.drop_index("uq_cliente_documento", table_name="cliente")
    op.drop_table("cliente")

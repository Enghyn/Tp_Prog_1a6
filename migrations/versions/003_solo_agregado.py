"""003_solo_agregado

Revision ID: 003_solo_agregado
Revises: 002_dominio_taller
Create Date: 2026-10-30 13:00:00.000000

Protección de tablas de solo-agregado mediante triggers PostgreSQL (RN-15).
Las tablas historial_estado_orden, movimiento_stock e historial_precio_repuesto
son de solo-agregado: se permiten INSERT pero NO UPDATE ni DELETE.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "003_solo_agregado"
down_revision: Union[str, None] = "002_dominio_taller"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLAS_SOLO_AGREGADO = [
    "historial_estado_orden",
    "movimiento_stock",
    "historial_precio_repuesto",
]

_FUNCION_BLOQUEO = "bloquear_modificacion_solo_agregado"


def upgrade() -> None:
    # Función PL/pgSQL compartida por los tres triggers
    op.execute("""
        CREATE OR REPLACE FUNCTION bloquear_modificacion_solo_agregado()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION
                'Tabla de solo-agregado: las filas no pueden modificarse ni eliminarse (tabla: %)',
                TG_TABLE_NAME;
        END;
        $$;
    """)

    # Trigger en cada tabla de solo-agregado
    for tabla in _TABLAS_SOLO_AGREGADO:
        op.execute(f"""
            CREATE TRIGGER trg_{tabla}_solo_agregado
            BEFORE UPDATE OR DELETE ON {tabla}
            FOR EACH ROW
            EXECUTE FUNCTION bloquear_modificacion_solo_agregado();
        """)


def downgrade() -> None:
    for tabla in _TABLAS_SOLO_AGREGADO:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{tabla}_solo_agregado ON {tabla};")

    op.execute(f"DROP FUNCTION IF EXISTS {_FUNCION_BLOQUEO}();")

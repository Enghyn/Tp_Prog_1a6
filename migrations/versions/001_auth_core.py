"""001_auth_core

Revision ID: 001_auth_core
Revises:
Create Date: 2026-10-30 12:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '001_auth_core'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'usuario',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('nombre', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('password_hash', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('activo', sa.Boolean(), nullable=False),
        sa.Column('debe_cambiar_password', sa.Boolean(), nullable=False),
        sa.Column('password_cambiada_en', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    op.create_table(
        'asignacion_rol',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('usuario_id', sa.Integer(), nullable=False),
        sa.Column('rol', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('desde', sa.DateTime(timezone=True), nullable=False),
        sa.Column('vence_en', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revocada_en', sa.DateTime(timezone=True), nullable=True),
        sa.Column('otorgada_por', sa.Integer(), nullable=True),
        sa.CheckConstraint("rol IN ('ADMIN', 'RECEPCION', 'MECANICO', 'CLIENTE')", name='ck_asignacion_rol_valido'),
        sa.ForeignKeyConstraint(['otorgada_por'], ['usuario.id'], ),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuario.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('uq_asignacion_rol_abierta', 'asignacion_rol', ['usuario_id', 'rol'], unique=True, postgresql_where=sa.text('revocada_en IS NULL'))
    op.create_table(
        'intento_acceso',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cuando', sa.DateTime(timezone=True), nullable=False),
        sa.Column('email', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('ip', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('exito', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_intento_acceso_email_ip_cuando', 'intento_acceso', ['email', 'ip', 'cuando'], unique=False)
    op.create_table(
        'evento_seguridad',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cuando', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('actor', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('accion', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('evento_seguridad')
    op.drop_index('ix_intento_acceso_email_ip_cuando', table_name='intento_acceso')
    op.drop_table('intento_acceso')
    op.drop_index('uq_asignacion_rol_abierta', table_name='asignacion_rol')
    op.drop_table('asignacion_rol')
    op.drop_table('usuario')

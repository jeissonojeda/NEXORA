"""0010_licensing_local

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-10-14 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'license_local_installation',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('installation_id', sa.String(length=64), nullable=False),
        sa.Column('fingerprint_hash', sa.String(length=128), nullable=False),
        sa.Column('machine_label', sa.String(length=120), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_license_local_installation_installation_id'),
        'license_local_installation',
        ['installation_id'],
        unique=True,
    )

    op.create_table(
        'license_local',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('license_key', sa.String(length=64), nullable=False),
        sa.Column('license_id', sa.String(length=64), nullable=True),
        sa.Column('customer_name', sa.String(length=150), nullable=True),
        sa.Column('plan_code', sa.String(length=50), nullable=True),
        sa.Column('license_type', sa.String(length=20), nullable=False),
        sa.Column('features_json', sa.Text(), nullable=False),
        sa.Column('max_installations', sa.Integer(), nullable=False),
        sa.Column('installation_id', sa.String(length=64), nullable=False),
        sa.Column('fingerprint_hash', sa.String(length=128), nullable=False),
        sa.Column('document_json', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('activated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('grace_days', sa.Integer(), nullable=False),
        sa.Column('updates_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('clock_rollback', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_license_local_license_key'), 'license_local', ['license_key'], unique=False
    )
    op.create_index(
        op.f('ix_license_local_installation_id'),
        'license_local',
        ['installation_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_license_local_installation_id'), table_name='license_local')
    op.drop_index(op.f('ix_license_local_license_key'), table_name='license_local')
    op.drop_table('license_local')
    op.drop_index(
        op.f('ix_license_local_installation_installation_id'),
        table_name='license_local_installation',
    )
    op.drop_table('license_local_installation')

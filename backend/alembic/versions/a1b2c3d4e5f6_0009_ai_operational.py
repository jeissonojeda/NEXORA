"""0009_ai_operational

Revision ID: a1b2c3d4e5f6
Revises: 30f2358766b0
Create Date: 2026-08-30 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '30f2358766b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ai_action_history',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('action_type', sa.String(length=50), nullable=False),
        sa.Column('action_name', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('payload_json', sa.Text(), nullable=True),
        sa.Column('result_json', sa.Text(), nullable=True),
        sa.Column('error_code', sa.String(length=50), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('idempotency_key', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_ai_action_history_action_type'), 'ai_action_history', ['action_type'], unique=False)
    op.create_index(op.f('ix_ai_action_history_idempotency_key'), 'ai_action_history', ['idempotency_key'], unique=False)
    op.create_index(op.f('ix_ai_action_history_status'), 'ai_action_history', ['status'], unique=False)
    op.create_index(op.f('ix_ai_action_history_user_id'), 'ai_action_history', ['user_id'], unique=False)

    op.create_table(
        'ai_invoice_scans',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('file_name', sa.String(length=255), nullable=True),
        sa.Column('mime_type', sa.String(length=100), nullable=True),
        sa.Column('supplier_name', sa.String(length=150), nullable=True),
        sa.Column('invoice_number', sa.String(length=100), nullable=True),
        sa.Column('total', sa.Numeric(14, 2), nullable=True),
        sa.Column('scan_data_json', sa.Text(), nullable=True),
        sa.Column('duplicate_of', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['duplicate_of'], ['ai_invoice_scans.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_ai_invoice_scans_user_id'), 'ai_invoice_scans', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_ai_invoice_scans_user_id'), table_name='ai_invoice_scans')
    op.drop_table('ai_invoice_scans')
    op.drop_index(op.f('ix_ai_action_history_user_id'), table_name='ai_action_history')
    op.drop_index(op.f('ix_ai_action_history_status'), table_name='ai_action_history')
    op.drop_index(op.f('ix_ai_action_history_idempotency_key'), table_name='ai_action_history')
    op.drop_index(op.f('ix_ai_action_history_action_type'), table_name='ai_action_history')
    op.drop_table('ai_action_history')

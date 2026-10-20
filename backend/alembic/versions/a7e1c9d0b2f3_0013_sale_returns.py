"""0013_sale_returns

Revision ID: a7e1c9d0b2f3
Revises: c1d2e3f4a5b6
Create Date: 2026-10-19 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7e1c9d0b2f3'
down_revision: Union[str, None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'sale_returns',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('return_number', sa.String(length=30), nullable=False),
        sa.Column('sale_id', sa.Uuid(), nullable=False),
        sa.Column('exchange_sale_id', sa.Uuid(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('return_type', sa.String(length=20), nullable=False),
        sa.Column('refund_method', sa.String(length=20), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column(
            'subtotal',
            sa.Numeric(precision=14, scale=2),
            nullable=False,
            server_default=sa.text('0'),
        ),
        sa.Column(
            'tax',
            sa.Numeric(precision=14, scale=2),
            nullable=False,
            server_default=sa.text('0'),
        ),
        sa.Column(
            'total',
            sa.Numeric(precision=14, scale=2),
            nullable=False,
            server_default=sa.text('0'),
        ),
        sa.Column(
            'credit_applied',
            sa.Numeric(precision=14, scale=2),
            nullable=False,
            server_default=sa.text('0'),
        ),
        sa.Column(
            'refunded_amount',
            sa.Numeric(precision=14, scale=2),
            nullable=False,
            server_default=sa.text('0'),
        ),
        sa.Column('idempotency_key', sa.String(length=100), nullable=True),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('COMPLETED', 'CANCELLED')",
            name='ck_sale_returns_status',
        ),
        sa.CheckConstraint(
            "return_type IN ('RETURN', 'EXCHANGE')",
            name='ck_sale_returns_type',
        ),
        sa.CheckConstraint(
            "refund_method IN ('CASH', 'CARD', 'TRANSFER', 'CREDIT')",
            name='ck_sale_returns_refund_method',
        ),
        sa.CheckConstraint('subtotal >= 0', name='ck_sale_returns_subtotal'),
        sa.CheckConstraint('tax >= 0', name='ck_sale_returns_tax'),
        sa.CheckConstraint('total >= 0', name='ck_sale_returns_total'),
        sa.CheckConstraint(
            'credit_applied >= 0', name='ck_sale_returns_credit_applied'
        ),
        sa.CheckConstraint(
            'refunded_amount >= 0', name='ck_sale_returns_refunded_amount'
        ),
        sa.ForeignKeyConstraint(
            ['created_by'],
            ['users.id'],
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['exchange_sale_id'],
            ['sales.id'],
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['sale_id'],
            ['sales.id'],
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_sale_returns_return_number'),
        'sale_returns',
        ['return_number'],
        unique=True,
    )
    op.create_index(
        op.f('ix_sale_returns_sale_id'), 'sale_returns', ['sale_id']
    )
    op.create_index(
        op.f('ix_sale_returns_exchange_sale_id'),
        'sale_returns',
        ['exchange_sale_id'],
    )
    op.create_index(
        op.f('ix_sale_returns_idempotency_key'),
        'sale_returns',
        ['idempotency_key'],
        unique=True,
    )

    op.create_table(
        'sale_return_items',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('sale_return_id', sa.Uuid(), nullable=False),
        sa.Column('sale_item_id', sa.Uuid(), nullable=False),
        sa.Column('product_id', sa.Uuid(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('unit_price', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            'discount',
            sa.Numeric(precision=12, scale=2),
            nullable=False,
            server_default=sa.text('0'),
        ),
        sa.Column(
            'tax',
            sa.Numeric(precision=12, scale=2),
            nullable=False,
            server_default=sa.text('0'),
        ),
        sa.Column(
            'tax_rate',
            sa.Numeric(precision=5, scale=2),
            nullable=False,
            server_default=sa.text('0'),
        ),
        sa.Column('tax_name', sa.String(length=80), nullable=True),
        sa.Column('subtotal', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('total', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('restock', sa.Boolean(), nullable=False),
        sa.Column('condition', sa.String(length=20), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.CheckConstraint('quantity > 0', name='ck_sale_return_items_qty'),
        sa.CheckConstraint(
            'unit_price >= 0', name='ck_sale_return_items_price'
        ),
        sa.CheckConstraint(
            'discount >= 0', name='ck_sale_return_items_discount'
        ),
        sa.CheckConstraint('tax >= 0', name='ck_sale_return_items_tax'),
        sa.CheckConstraint(
            'subtotal >= 0', name='ck_sale_return_items_subtotal'
        ),
        sa.CheckConstraint('total >= 0', name='ck_sale_return_items_total'),
        sa.CheckConstraint(
            "condition IN ('RESALE', 'DAMAGED', 'REVIEW')",
            name='ck_sale_return_items_condition',
        ),
        sa.ForeignKeyConstraint(
            ['product_id'],
            ['products.id'],
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['sale_item_id'],
            ['sale_items.id'],
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['sale_return_id'],
            ['sale_returns.id'],
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_sale_return_items_sale_return_id'),
        'sale_return_items',
        ['sale_return_id'],
    )
    op.create_index(
        op.f('ix_sale_return_items_sale_item_id'),
        'sale_return_items',
        ['sale_item_id'],
    )
    op.create_index(
        op.f('ix_sale_return_items_product_id'),
        'sale_return_items',
        ['product_id'],
    )
    op.create_index(
        'ux_sale_return_items_sale_item',
        'sale_return_items',
        ['sale_return_id', 'sale_item_id'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        'ux_sale_return_items_sale_item', table_name='sale_return_items'
    )
    op.drop_index(
        op.f('ix_sale_return_items_product_id'),
        table_name='sale_return_items',
    )
    op.drop_index(
        op.f('ix_sale_return_items_sale_item_id'),
        table_name='sale_return_items',
    )
    op.drop_index(
        op.f('ix_sale_return_items_sale_return_id'),
        table_name='sale_return_items',
    )
    op.drop_table('sale_return_items')
    op.drop_index(
        op.f('ix_sale_returns_idempotency_key'), table_name='sale_returns'
    )
    op.drop_index(
        op.f('ix_sale_returns_exchange_sale_id'), table_name='sale_returns'
    )
    op.drop_index(op.f('ix_sale_returns_sale_id'), table_name='sale_returns')
    op.drop_index(
        op.f('ix_sale_returns_return_number'), table_name='sale_returns'
    )
    op.drop_table('sale_returns')

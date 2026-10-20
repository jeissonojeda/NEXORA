"""0012_taxes

Revision ID: c1d2e3f4a5b6
Revises: 79dbd4f1b7c4
Create Date: 2026-10-14 18:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, None] = '79dbd4f1b7c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'taxes',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('rate', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.CheckConstraint('rate >= 0', name='ck_taxes_rate_non_negative'),
        sa.CheckConstraint('rate <= 100', name='ck_taxes_rate_max'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_taxes_name'), 'taxes', ['name'], unique=True)

    op.add_column('categories', sa.Column('tax_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        'fk_categories_tax_id_taxes',
        'categories',
        'taxes',
        ['tax_id'],
        ['id'],
        ondelete='SET NULL',
    )

    op.add_column('products', sa.Column('tax_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        'fk_products_tax_id_taxes',
        'products',
        'taxes',
        ['tax_id'],
        ['id'],
        ondelete='SET NULL',
    )

    op.add_column(
        'sale_items',
        sa.Column(
            'tax_rate',
            sa.Numeric(precision=5, scale=2),
            nullable=False,
            server_default=sa.text('0'),
        ),
    )
    op.add_column(
        'sale_items', sa.Column('tax_name', sa.String(length=80), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('sale_items', 'tax_name')
    op.drop_column('sale_items', 'tax_rate')
    op.drop_constraint('fk_products_tax_id_taxes', 'products', type_='foreignkey')
    op.drop_column('products', 'tax_id')
    op.drop_constraint('fk_categories_tax_id_taxes', 'categories', type_='foreignkey')
    op.drop_column('categories', 'tax_id')
    op.drop_index(op.f('ix_taxes_name'), table_name='taxes')
    op.drop_table('taxes')

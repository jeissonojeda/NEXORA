"""0011_settings_and_product_fields

Revision ID: 79dbd4f1b7c4
Revises: b2c3d4e5f6a7
Create Date: 2026-10-14 16:44:13.510644
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '79dbd4f1b7c4'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'products', sa.Column('unit', sa.String(length=20), nullable=True)
    )
    op.add_column(
        'products',
        sa.Column(
            'profit_percent',
            sa.Numeric(precision=6, scale=2),
            nullable=False,
            server_default=sa.text('0'),
        ),
    )
    op.create_check_constraint(
        'ck_products_profit_percent', 'products', 'profit_percent >= 0'
    )

    op.create_table(
        'settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('currency_code', sa.String(length=3), nullable=False),
        sa.Column('currency_symbol', sa.String(length=5), nullable=False),
        sa.Column('currency_locale', sa.String(length=10), nullable=False),
        sa.Column('decimal_places', sa.Integer(), nullable=False),
        sa.Column('use_thousand_separator', sa.Boolean(), nullable=False),
        sa.Column('business_name', sa.String(length=150), nullable=True),
        sa.Column('business_tax_id', sa.String(length=50), nullable=True),
        sa.Column('business_address', sa.String(length=250), nullable=True),
        sa.Column('business_phone', sa.String(length=50), nullable=True),
        sa.Column('business_email', sa.String(length=100), nullable=True),
        sa.Column('business_logo_path', sa.String(length=255), nullable=True),
        sa.Column('printer_name', sa.String(length=150), nullable=True),
        sa.Column('paper_width', sa.String(length=10), nullable=False),
        sa.Column('print_copies', sa.Integer(), nullable=False),
        sa.Column('print_font_size', sa.String(length=10), nullable=False),
        sa.Column('print_show_logo', sa.Boolean(), nullable=False),
        sa.Column('print_show_contact', sa.Boolean(), nullable=False),
        sa.Column('print_show_tax_id', sa.Boolean(), nullable=False),
        sa.Column('print_footer_text', sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('settings')
    op.drop_constraint(
        'ck_products_profit_percent', 'products', type_='check'
    )
    op.drop_column('products', 'profit_percent')
    op.drop_column('products', 'unit')

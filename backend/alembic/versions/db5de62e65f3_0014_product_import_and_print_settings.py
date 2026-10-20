"""0014_product_import_and_print_settings

Revision ID: db5de62e65f3
Revises: a7e1c9d0b2f3
Create Date: 2026-10-19 09:52:19.570982

Idempotente: cada operación comprueba el esquema real antes de aplicarse, de
modo que puede ejecutarse en bases donde parte de las columnas ya existían de
versiones anteriores sin fallar con DuplicateColumn.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'db5de62e65f3'
down_revision: Union[str, None] = 'a7e1c9d0b2f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table: str) -> bool:
    bind = op.get_bind()
    return sa.inspect(bind).has_table(table)


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(table):
        return False
    return column in {c["name"] for c in sa.inspect(bind).get_columns(table)}


def _index_exists(table: str, index: str) -> bool:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(table):
        return False
    return index in {i["name"] for i in sa.inspect(bind).get_indexes(table)}


# Columnas de impresión/logo a añadir a `settings`.
_SETTINGS_COLUMNS: list[tuple[str, sa.types.TypeEngine, str | None]] = [
    ("business_legal_name", sa.String(length=255), None),
    ("business_header_text", sa.Text(), None),
    ("business_additional_info", sa.Text(), None),
    ("print_logo_size", sa.String(length=10), None),
    ("print_logo_align", sa.String(length=10), None),
    ("print_show_logo", sa.Boolean(), "true"),
    ("print_show_company_name", sa.Boolean(), "true"),
    ("print_show_nit", sa.Boolean(), "true"),
    ("print_show_address", sa.Boolean(), "true"),
    ("print_show_phone", sa.Boolean(), "true"),
    ("print_show_email", sa.Boolean(), "true"),
    ("print_show_city", sa.Boolean(), "true"),
    ("print_show_header_text", sa.Boolean(), "true"),
    ("print_show_additional_info", sa.Boolean(), "true"),
    ("print_show_legal_footer", sa.Boolean(), "true"),
    ("print_show_customer_info", sa.Boolean(), "true"),
    ("print_show_seller", sa.Boolean(), "true"),
    ("print_show_payment_method", sa.Boolean(), "true"),
    ("print_show_sale_date", sa.Boolean(), "true"),
    ("print_show_due_date", sa.Boolean(), "true"),
    ("print_show_barcode", sa.Boolean(), "false"),
    ("print_show_unit", sa.Boolean(), "true"),
    ("print_show_discount", sa.Boolean(), "true"),
    ("print_show_tax", sa.Boolean(), "true"),
    ("print_alignment", sa.String(length=20), None),
    ("print_margin_mm", sa.Integer(), None),
    ("logo_filename", sa.String(length=255), None),
    ("logo_mime_type", sa.String(length=50), None),
    ("logo_size_bytes", sa.Integer(), None),
]


def upgrade() -> None:
    # product_import_batches
    if not _table_exists("product_import_batches"):
        op.create_table(
            'product_import_batches',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('file_name', sa.String(length=255), nullable=False),
            sa.Column('row_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('updated_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('skipped_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('rejected_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('details', sa.Text(), nullable=True),
            sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='RESTRICT'),
            sa.PrimaryKeyConstraint('id'),
        )
    if not _index_exists("product_import_batches", "ix_product_import_batches_created_at"):
        op.create_index(
            op.f('ix_product_import_batches_created_at'),
            'product_import_batches',
            ['created_at'],
            unique=False,
        )

    # settings: impresión de facturas + logo (idempotente por columna)
    for name, coltype, default in _SETTINGS_COLUMNS:
        if _column_exists("settings", name):
            continue
        kwargs = {"server_default": sa.text(default)} if default is not None else {}
        op.add_column('settings', sa.Column(name, coltype, nullable=True, **kwargs))


def downgrade() -> None:
    # revert settings
    for name, _coltype, _default in reversed(_SETTINGS_COLUMNS):
        if _column_exists("settings", name):
            op.drop_column('settings', name)
    if _index_exists("product_import_batches", "ix_product_import_batches_created_at"):
        op.drop_index(op.f('ix_product_import_batches_created_at'), table_name='product_import_batches')
    if _table_exists("product_import_batches"):
        op.drop_table('product_import_batches')

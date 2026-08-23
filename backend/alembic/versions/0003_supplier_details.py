"""supplier details: identification, address, city, notes

Revision ID: 0003_supplier_details
Revises: 0002_catalog
Create Date: 2026-08-22
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_supplier_details"
down_revision = "0002_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("suppliers") as batch:
        batch.add_column(
            sa.Column("identification", sa.String(length=50), nullable=True)
        )
        batch.add_column(sa.Column("address", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("city", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("notes", sa.Text(), nullable=True))

    op.create_index(
        "ix_suppliers_identification", "suppliers", ["identification"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_suppliers_identification", table_name="suppliers")

    with op.batch_alter_table("suppliers") as batch:
        batch.drop_column("notes")
        batch.drop_column("city")
        batch.drop_column("address")
        batch.drop_column("identification")

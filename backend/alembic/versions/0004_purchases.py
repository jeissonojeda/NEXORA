"""purchases and purchase_items + movement reference_type

Revision ID: 0004_purchases
Revises: 0003_supplier_details
Create Date: 2026-08-23
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_purchases"
down_revision = "0003_supplier_details"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "purchases",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "supplier_id",
            sa.Uuid(),
            sa.ForeignKey("suppliers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("purchase_number", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False),
        sa.Column("discount", sa.Numeric(14, 2), nullable=False),
        sa.Column("tax", sa.Numeric(14, 2), nullable=False),
        sa.Column("total", sa.Numeric(14, 2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'CONFIRMED', 'CANCELLED')",
            name="ck_purchases_status",
        ),
        sa.CheckConstraint("subtotal >= 0", name="ck_purchases_subtotal"),
        sa.CheckConstraint("discount >= 0", name="ck_purchases_discount"),
        sa.CheckConstraint("tax >= 0", name="ck_purchases_tax"),
        sa.CheckConstraint("total >= 0", name="ck_purchases_total"),
    )
    op.create_index(
        "ix_purchases_purchase_number", "purchases", ["purchase_number"],
        unique=True,
    )
    op.create_index("ix_purchases_supplier_id", "purchases", ["supplier_id"])

    op.create_table(
        "purchase_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "purchase_id",
            sa.Uuid(),
            sa.ForeignKey("purchases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            sa.Uuid(),
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("discount", sa.Numeric(12, 2), nullable=False),
        sa.Column("tax", sa.Numeric(12, 2), nullable=False),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False),
        sa.Column("total", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "quantity > 0", name="ck_purchase_items_quantity_positive"
        ),
        sa.CheckConstraint("unit_cost >= 0", name="ck_purchase_items_unit_cost"),
        sa.CheckConstraint("discount >= 0", name="ck_purchase_items_discount"),
        sa.CheckConstraint("tax >= 0", name="ck_purchase_items_tax"),
        sa.CheckConstraint("subtotal >= 0", name="ck_purchase_items_subtotal"),
        sa.CheckConstraint("total >= 0", name="ck_purchase_items_total"),
    )
    op.create_index(
        "ix_purchase_items_purchase_id", "purchase_items", ["purchase_id"]
    )
    op.create_index(
        "ix_purchase_items_product_id", "purchase_items", ["product_id"]
    )

    with op.batch_alter_table("inventory_movements") as batch:
        batch.add_column(sa.Column("reference_type", sa.String(length=50),
                                   nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("inventory_movements") as batch:
        batch.drop_column("reference_type")

    op.drop_index("ix_purchase_items_product_id", table_name="purchase_items")
    op.drop_index("ix_purchase_items_purchase_id", table_name="purchase_items")
    op.drop_table("purchase_items")

    op.drop_index("ix_purchases_supplier_id", table_name="purchases")
    op.drop_index("ix_purchases_purchase_number", table_name="purchases")
    op.drop_table("purchases")

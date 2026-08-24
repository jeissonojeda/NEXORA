"""sales and sale_items

Revision ID: 0006_sales
Revises: 0005_customers_receivables
Create Date: 2026-08-23
"""

import sqlalchemy as sa
from alembic import op

revision = "0006_sales"
down_revision = "0005_customers_receivables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sales",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("sale_number", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "customer_id",
            sa.Uuid(),
            sa.ForeignKey("customers.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("payment_method", sa.String(length=20), nullable=False),
        sa.Column("amount_paid", sa.Numeric(14, 2), nullable=False),
        sa.Column("change_due", sa.Numeric(14, 2), nullable=False),
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
            name="ck_sales_status",
        ),
        sa.CheckConstraint(
            "payment_method IN ('CASH', 'CARD', 'TRANSFER', 'CREDIT')",
            name="ck_sales_payment_method",
        ),
        sa.CheckConstraint("subtotal >= 0", name="ck_sales_subtotal"),
        sa.CheckConstraint("discount >= 0", name="ck_sales_discount"),
        sa.CheckConstraint("tax >= 0", name="ck_sales_tax"),
        sa.CheckConstraint("total >= 0", name="ck_sales_total"),
        sa.CheckConstraint("amount_paid >= 0", name="ck_sales_amount_paid"),
        sa.CheckConstraint("change_due >= 0", name="ck_sales_change_due"),
    )
    op.create_index("ix_sales_sale_number", "sales", ["sale_number"], unique=True)
    op.create_index("ix_sales_customer_id", "sales", ["customer_id"])

    op.create_table(
        "sale_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "sale_id",
            sa.Uuid(),
            sa.ForeignKey("sales.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            sa.Uuid(),
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
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
            "quantity > 0", name="ck_sale_items_quantity_positive"
        ),
        sa.CheckConstraint("unit_price >= 0", name="ck_sale_items_unit_price"),
        sa.CheckConstraint("discount >= 0", name="ck_sale_items_discount"),
        sa.CheckConstraint("tax >= 0", name="ck_sale_items_tax"),
        sa.CheckConstraint("subtotal >= 0", name="ck_sale_items_subtotal"),
        sa.CheckConstraint("total >= 0", name="ck_sale_items_total"),
    )
    op.create_index("ix_sale_items_sale_id", "sale_items", ["sale_id"])
    op.create_index("ix_sale_items_product_id", "sale_items", ["product_id"])


def downgrade() -> None:
    op.drop_index("ix_sale_items_product_id", table_name="sale_items")
    op.drop_index("ix_sale_items_sale_id", table_name="sale_items")
    op.drop_table("sale_items")

    op.drop_index("ix_sales_customer_id", table_name="sales")
    op.drop_index("ix_sales_sale_number", table_name="sales")
    op.drop_table("sales")

"""cash_registers and cash_movements

Revision ID: 0007_cash
Revises: 0006_sales
Create Date: 2026-08-24
"""

import sqlalchemy as sa
from alembic import op

revision = "0007_cash"
down_revision = "0006_sales"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cash_registers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("opening_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "opened_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "closed_by_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("expected_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("counted_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("difference", sa.Numeric(14, 2), nullable=True),
        sa.CheckConstraint(
            "status IN ('OPEN', 'CLOSED', 'CANCELLED')",
            name="ck_cash_registers_status",
        ),
        sa.CheckConstraint(
            "opening_amount >= 0", name="ck_cash_registers_opening_non_negative"
        ),
        sa.CheckConstraint(
            "expected_amount IS NULL OR expected_amount >= 0",
            name="ck_cash_registers_expected_non_negative",
        ),
        sa.CheckConstraint(
            "counted_amount IS NULL OR counted_amount >= 0",
            name="ck_cash_registers_counted_non_negative",
        ),
    )
    op.create_index(
        "ix_cash_registers_user_id", "cash_registers", ["user_id"]
    )
    op.create_index(
        "ux_cash_registers_user_open",
        "cash_registers",
        ["user_id"],
        unique=True,
        sqlite_where=sa.text("status = 'OPEN'"),
        postgresql_where=sa.text("status = 'OPEN'"),
    )

    op.create_table(
        "cash_movements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "register_id",
            sa.Uuid(),
            sa.ForeignKey("cash_registers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("movement_type", sa.String(length=30), nullable=False),
        sa.Column("payment_method", sa.String(length=20), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("reference_type", sa.String(length=30), nullable=True),
        sa.Column("reference_id", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "movement_type IN ('OPENING', 'SALE', 'RECEIVABLE_PAYMENT',"
            " 'CASH_IN', 'CASH_OUT', 'ADJUSTMENT')",
            name="ck_cash_movements_type",
        ),
        sa.CheckConstraint(
            "payment_method IS NULL OR payment_method IN"
            " ('CASH', 'CARD', 'TRANSFER')",
            name="ck_cash_movements_method",
        ),
        sa.CheckConstraint(
            "(movement_type = 'OPENING' AND amount >= 0)"
            " OR (movement_type <> 'OPENING' AND amount > 0)",
            name="ck_cash_movements_amount_positive",
        ),
    )
    op.create_index(
        "ix_cash_movements_register_id", "cash_movements", ["register_id"]
    )
    op.create_index(
        "ux_cash_movements_reference",
        "cash_movements",
        ["reference_type", "reference_id"],
        unique=True,
        sqlite_where=sa.text("reference_id IS NOT NULL"),
        postgresql_where=sa.text("reference_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ux_cash_movements_reference",
        table_name="cash_movements",
    )
    op.drop_index("ix_cash_movements_register_id", table_name="cash_movements")
    op.drop_table("cash_movements")

    op.drop_index(
        "ux_cash_registers_user_open", table_name="cash_registers"
    )
    op.drop_index("ix_cash_registers_user_id", table_name="cash_registers")
    op.drop_table("cash_registers")

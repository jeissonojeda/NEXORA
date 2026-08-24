"""customers, receivable_accounts and receivable_payments

Revision ID: 0005_customers_receivables
Revises: 0004_purchases
Create Date: 2026-08-23
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_customers_receivables"
down_revision = "0004_purchases"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("identification", sa.String(length=50), nullable=True),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("credit_enabled", sa.Boolean(), nullable=False),
        sa.Column("credit_limit", sa.Numeric(14, 2), nullable=False),
        sa.Column("current_balance", sa.Numeric(14, 2), nullable=False),
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
        sa.CheckConstraint(
            "credit_limit >= 0", name="ck_customers_credit_limit"
        ),
        sa.CheckConstraint(
            "current_balance >= 0", name="ck_customers_current_balance"
        ),
        sa.CheckConstraint(
            "NOT credit_enabled OR current_balance <= credit_limit",
            name="ck_customers_balance_within_limit",
        ),
    )
    op.create_index(
        "ix_customers_identification", "customers", ["identification"],
        unique=True,
    )
    op.create_index("ix_customers_name", "customers", ["name"])

    op.create_table(
        "receivable_accounts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "customer_id",
            sa.Uuid(),
            sa.ForeignKey("customers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("reference_type", sa.String(length=30), nullable=False),
        sa.Column("reference_id", sa.String(length=100), nullable=True),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("original_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("paid_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("balance", sa.Numeric(14, 2), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
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
        sa.CheckConstraint(
            "status IN ('OPEN', 'PARTIALLY_PAID', 'PAID', 'CANCELLED')",
            name="ck_receivable_accounts_status",
        ),
        sa.CheckConstraint(
            "original_amount > 0",
            name="ck_receivable_accounts_original_positive",
        ),
        sa.CheckConstraint(
            "paid_amount >= 0",
            name="ck_receivable_accounts_paid_non_negative",
        ),
        sa.CheckConstraint(
            "paid_amount <= original_amount",
            name="ck_receivable_accounts_paid_within_original",
        ),
        sa.CheckConstraint(
            "balance = original_amount - paid_amount",
            name="ck_receivable_accounts_balance_math",
        ),
        sa.CheckConstraint(
            "balance >= 0",
            name="ck_receivable_accounts_balance_non_negative",
        ),
    )
    op.create_index(
        "ix_receivable_accounts_customer_id", "receivable_accounts",
        ["customer_id"],
    )

    op.create_table(
        "receivable_payments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "receivable_account_id",
            sa.Uuid(),
            sa.ForeignKey("receivable_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("payment_method", sa.String(length=20), nullable=False),
        sa.Column("reference", sa.String(length=100), nullable=True),
        sa.Column("idempotency_key", sa.String(length=100), nullable=True),
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
        sa.CheckConstraint(
            "payment_method IN ('CASH', 'CARD', 'TRANSFER', 'OTHER')",
            name="ck_receivable_payments_method",
        ),
        sa.CheckConstraint(
            "amount > 0", name="ck_receivable_payments_amount_positive"
        ),
    )
    op.create_index(
        "ix_receivable_payments_receivable_account_id", "receivable_payments",
        ["receivable_account_id"],
    )
    op.create_index(
        "ix_receivable_payments_idempotency_key", "receivable_payments",
        ["idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_receivable_payments_idempotency_key", table_name="receivable_payments"
    )
    op.drop_index(
        "ix_receivable_payments_receivable_account_id",
        table_name="receivable_payments",
    )
    op.drop_table("receivable_payments")

    op.drop_index(
        "ix_receivable_accounts_customer_id", table_name="receivable_accounts"
    )
    op.drop_table("receivable_accounts")

    op.drop_index("ix_customers_name", table_name="customers")
    op.drop_index("ix_customers_identification", table_name="customers")
    op.drop_table("customers")

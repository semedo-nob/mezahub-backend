"""add payment participants and payouts

Revision ID: add_payment_participants_and_payouts
Revises: add_mpesa_payment_fields
Create Date: 2026-04-01

"""

from alembic import op
import sqlalchemy as sa


revision = "add_payment_participants_and_payouts"
down_revision = "add_mpesa_payment_fields"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("payments", schema=None) as batch_op:
        batch_op.add_column(sa.Column("customer_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("restaurant_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("rider_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("delivery_fee", sa.Numeric(precision=10, scale=2), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("total_amount", sa.Numeric(precision=10, scale=2), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("restaurant_paid", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(
            sa.Column("rider_paid", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(sa.Column("restaurant_payout_date", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("rider_payout_date", sa.DateTime(), nullable=True))
        batch_op.create_index(batch_op.f("ix_payments_customer_id"), ["customer_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_payments_restaurant_id"), ["restaurant_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_payments_rider_id"), ["rider_id"], unique=False)
        batch_op.create_foreign_key(batch_op.f("fk_payments_customer_id_users"), "users", ["customer_id"], ["id"])
        batch_op.create_foreign_key(
            batch_op.f("fk_payments_restaurant_id_restaurants"), "restaurants", ["restaurant_id"], ["id"]
        )
        batch_op.create_foreign_key(batch_op.f("fk_payments_rider_id_riders"), "riders", ["rider_id"], ["id"])

    op.create_table(
        "payouts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("payment_id", sa.Integer(), nullable=False),
        sa.Column("recipient_type", sa.String(length=20), nullable=False),
        sa.Column("recipient_id", sa.Integer(), nullable=False),
        sa.Column("recipient_phone", sa.String(length=20), nullable=False),
        sa.Column("amount", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("conversation_id", sa.String(length=120), nullable=True),
        sa.Column("originator_conversation_id", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("result_code", sa.String(length=20), nullable=True),
        sa.Column("result_desc", sa.Text(), nullable=True),
        sa.Column("payout_date", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], name=op.f("fk_payouts_payment_id_payments")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payouts")),
    )
    with op.batch_alter_table("payouts", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_payouts_payment_id"), ["payment_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_payouts_recipient_id"), ["recipient_id"], unique=False)


def downgrade():
    with op.batch_alter_table("payouts", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_payouts_recipient_id"))
        batch_op.drop_index(batch_op.f("ix_payouts_payment_id"))
    op.drop_table("payouts")

    with op.batch_alter_table("payments", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("fk_payments_rider_id_riders"), type_="foreignkey")
        batch_op.drop_constraint(
            batch_op.f("fk_payments_restaurant_id_restaurants"), type_="foreignkey"
        )
        batch_op.drop_constraint(batch_op.f("fk_payments_customer_id_users"), type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_payments_rider_id"))
        batch_op.drop_index(batch_op.f("ix_payments_restaurant_id"))
        batch_op.drop_index(batch_op.f("ix_payments_customer_id"))
        batch_op.drop_column("rider_payout_date")
        batch_op.drop_column("restaurant_payout_date")
        batch_op.drop_column("rider_paid")
        batch_op.drop_column("restaurant_paid")
        batch_op.drop_column("total_amount")
        batch_op.drop_column("delivery_fee")
        batch_op.drop_column("rider_id")
        batch_op.drop_column("restaurant_id")
        batch_op.drop_column("customer_id")

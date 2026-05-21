"""add mpesa payment fields

Revision ID: add_mpesa_payment_fields
Revises: add_restaurant_logo_image
Create Date: 2026-04-01

"""

from alembic import op
import sqlalchemy as sa


revision = "add_mpesa_payment_fields"
down_revision = "add_restaurant_logo_image"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("payments", schema=None) as batch_op:
        batch_op.add_column(sa.Column("phone_number", sa.String(length=20), nullable=True))
        batch_op.add_column(
            sa.Column("checkout_request_id", sa.String(length=120), nullable=True)
        )
        batch_op.add_column(
            sa.Column("merchant_request_id", sa.String(length=120), nullable=True)
        )
        batch_op.add_column(sa.Column("conversation_id", sa.String(length=120), nullable=True))
        batch_op.add_column(
            sa.Column("originator_conversation_id", sa.String(length=120), nullable=True)
        )
        batch_op.add_column(
            sa.Column("mpesa_receipt_number", sa.String(length=120), nullable=True)
        )
        batch_op.add_column(sa.Column("result_code", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("result_desc", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("transaction_date", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("raw_callback", sa.JSON(), nullable=True))
        batch_op.add_column(
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now())
        )
        batch_op.create_index(
            batch_op.f("ix_payments_checkout_request_id"),
            ["checkout_request_id"],
            unique=True,
        )


def downgrade():
    with op.batch_alter_table("payments", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_payments_checkout_request_id"))
        batch_op.drop_column("updated_at")
        batch_op.drop_column("raw_callback")
        batch_op.drop_column("transaction_date")
        batch_op.drop_column("result_desc")
        batch_op.drop_column("result_code")
        batch_op.drop_column("mpesa_receipt_number")
        batch_op.drop_column("originator_conversation_id")
        batch_op.drop_column("conversation_id")
        batch_op.drop_column("merchant_request_id")
        batch_op.drop_column("checkout_request_id")
        batch_op.drop_column("phone_number")

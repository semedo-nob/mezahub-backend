"""add order contact_name and contact_phone

Revision ID: add_order_contact
Revises: 81e80fdc6e87
Create Date: 2026-03-13

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_order_contact'
down_revision = '81e80fdc6e87'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('orders', sa.Column('contact_name', sa.String(length=120), nullable=True))
    op.add_column('orders', sa.Column('contact_phone', sa.String(length=30), nullable=True))


def downgrade():
    op.drop_column('orders', 'contact_phone')
    op.drop_column('orders', 'contact_name')

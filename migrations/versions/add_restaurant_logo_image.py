"""add restaurant logo_image

Revision ID: add_restaurant_logo_image
Revises: add_order_contact
Create Date: 2026-03-24

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_restaurant_logo_image'
down_revision = 'add_order_contact'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('restaurants', sa.Column('logo_image', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('restaurants', 'logo_image')

"""add vendor_gift_claimed to checkin_list

Revision ID: c3d4e5f6a7b8
Revises: a1b2c3d4e5f6
Create Date: 2026-05-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3d4e5f6a7b8'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('checkin_list', sa.Column('vendor_gift_claimed', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.alter_column('checkin_list', 'vendor_gift_claimed', server_default=None)


def downgrade():
    op.drop_column('checkin_list', 'vendor_gift_claimed')

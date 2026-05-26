"""add vendor_gift_claimed to checkin_list

Revision ID: c3d4e5f6a7b8
Revises: 9a8b7c6d5e4f
Create Date: 2026-05-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3d4e5f6a7b8'
down_revision = '9a8b7c6d5e4f'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('checkin_list', sa.Column('vendor_gift_claimed', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.alter_column('checkin_list', 'vendor_gift_claimed', server_default=None)


def downgrade():
    op.drop_column('checkin_list', 'vendor_gift_claimed')

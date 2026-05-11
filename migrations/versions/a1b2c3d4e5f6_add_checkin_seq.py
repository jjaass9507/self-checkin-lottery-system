"""add checkin_seq to checkin_list

Revision ID: a1b2c3d4e5f6
Revises: b7f3e2a91c08
Create Date: 2026-05-12 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'b7f3e2a91c08'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('checkin_list', sa.Column('checkin_seq', sa.String(10), nullable=True))


def downgrade():
    op.drop_column('checkin_list', 'checkin_seq')

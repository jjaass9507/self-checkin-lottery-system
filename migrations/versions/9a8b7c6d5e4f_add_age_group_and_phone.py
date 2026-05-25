"""add age_group and phone

Revision ID: 9a8b7c6d5e4f
Revises: c9f1e2d3a4b5
Create Date: 2026-05-25 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9a8b7c6d5e4f'
down_revision = 'c9f1e2d3a4b5'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('checkin_list', schema=None) as batch_op:
        batch_op.add_column(sa.Column('age_group', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('phone', sa.String(length=30), nullable=True))


def downgrade():
    with op.batch_alter_table('checkin_list', schema=None) as batch_op:
        batch_op.drop_column('phone')
        batch_op.drop_column('age_group')

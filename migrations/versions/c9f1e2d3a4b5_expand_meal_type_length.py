"""expand meal_type length

Revision ID: c9f1e2d3a4b5
Revises: a1b2c3d4e5f6
Create Date: 2026-05-25 14:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c9f1e2d3a4b5'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('checkin_list', schema=None) as batch_op:
        batch_op.alter_column(
            'meal_type',
            existing_type=sa.String(length=10),
            type_=sa.String(length=100),
            existing_nullable=True,
        )


def downgrade():
    with op.batch_alter_table('checkin_list', schema=None) as batch_op:
        batch_op.alter_column(
            'meal_type',
            existing_type=sa.String(length=100),
            type_=sa.String(length=10),
            existing_nullable=True,
        )

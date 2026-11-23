"""add event_editions table (歷史版次)

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-11-23

"""
from alembic import op
import sqlalchemy as sa


revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'event_editions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('archived_at', sa.DateTime(), nullable=False),
        sa.Column('total_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('checked_in_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('winner_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('draw_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('data', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('event_editions')

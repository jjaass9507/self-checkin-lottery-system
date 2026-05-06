"""add app_settings table

Revision ID: b7f3e2a91c08
Revises: 651c6c783d29
Create Date: 2026-05-05 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'b7f3e2a91c08'
down_revision = '651c6c783d29'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'app_settings',
        sa.Column('key',   sa.String(50),  nullable=False),
        sa.Column('value', sa.String(200), nullable=False),
        sa.PrimaryKeyConstraint('key')
    )
    # 預設：抽獎功能啟用
    op.execute("INSERT INTO app_settings (key, value) VALUES ('lottery_enabled', 'true')")


def downgrade():
    op.drop_table('app_settings')

"""add one-time turn soon notification flag

Revision ID: 6e2f9a4b1c80
Revises: 5d8a3b1c2e70
"""
from alembic import op
import sqlalchemy as sa

revision = "6e2f9a4b1c80"
down_revision = "5d8a3b1c2e70"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("bookings", sa.Column("turn_soon_notified", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column("bookings", "turn_soon_notified")
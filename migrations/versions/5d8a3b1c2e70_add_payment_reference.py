"""add manual payment method and reference

Revision ID: 5d8a3b1c2e70
Revises: 4c1f2e8a7b91
"""
from alembic import op
import sqlalchemy as sa

revision = "5d8a3b1c2e70"
down_revision = "4c1f2e8a7b91"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("bookings", sa.Column("payment_method", sa.String(length=20), nullable=True))
    op.add_column("bookings", sa.Column("payment_reference", sa.String(length=120), nullable=True))


def downgrade():
    op.drop_column("bookings", "payment_reference")
    op.drop_column("bookings", "payment_method")
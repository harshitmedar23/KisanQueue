"""add centre-specific mandi prices

Revision ID: 8a4b2c1d6e50
Revises: 7f3a1d2c9e40
"""
from alembic import op
import sqlalchemy as sa


revision = "8a4b2c1d6e50"
down_revision = "7f3a1d2c9e40"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {item["name"] for item in inspector.get_columns("mandi_prices")}
    if "centre_id" not in columns:
        op.add_column("mandi_prices", sa.Column("centre_id", sa.Integer(), nullable=True))
        op.create_index("ix_mandi_prices_centre_id", "mandi_prices", ["centre_id"])


def downgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {item["name"] for item in inspector.get_columns("mandi_prices")}
    if "centre_id" in columns:
        op.drop_index("ix_mandi_prices_centre_id", table_name="mandi_prices")
        op.drop_column("mandi_prices", "centre_id")
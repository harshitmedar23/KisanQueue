"""add optional transport booking support

Revision ID: 4c1f2e8a7b91
Revises: 08dd03f5a143
Create Date: 2026-09-10 23:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "4c1f2e8a7b91"
down_revision = "08dd03f5a143"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "vehicles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("driver_name", sa.String(length=120), nullable=False),
        sa.Column("driver_phone", sa.String(length=15), nullable=False),
        sa.Column("capacity_kg", sa.Float(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "transport_bookings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("booking_id", sa.Integer(), nullable=False),
        sa.Column("vehicle_id", sa.Integer(), nullable=True),
        sa.Column("pickup_location", sa.Text(), nullable=False),
        sa.Column("estimated_distance_km", sa.Float(), nullable=True),
        sa.Column("fare_amount", sa.Float(), nullable=False),
        sa.Column("payment_status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="requested"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"]),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("booking_id"),
    )


def downgrade():
    op.drop_table("transport_bookings")
    op.drop_table("vehicles")

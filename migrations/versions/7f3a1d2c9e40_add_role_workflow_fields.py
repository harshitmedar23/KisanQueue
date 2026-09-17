"""add role workflow and driver lifecycle fields

Revision ID: 7f3a1d2c9e40
Revises: 6e2f9a4b1c80
"""
from alembic import op
import sqlalchemy as sa


revision = "7f3a1d2c9e40"
down_revision = "6e2f9a4b1c80"
branch_labels = None
depends_on = None


def _add_if_missing(table_name, column):
    inspector = sa.inspect(op.get_bind())
    existing = {item["name"] for item in inspector.get_columns(table_name)}
    if column.name not in existing:
        op.add_column(table_name, column)


def upgrade():
    _add_if_missing("users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    _add_if_missing("users", sa.Column("assigned_centre_id", sa.Integer(), nullable=True))

    _add_if_missing("bookings", sa.Column("approval_status", sa.String(length=20), nullable=False, server_default="approved"))
    _add_if_missing("bookings", sa.Column("rejection_reason", sa.String(length=200), nullable=True))
    _add_if_missing("bookings", sa.Column("approved_at", sa.DateTime(), nullable=True))

    _add_if_missing("vehicles", sa.Column("centre_id", sa.Integer(), nullable=True))
    _add_if_missing("vehicles", sa.Column("driver_status", sa.String(length=20), nullable=False, server_default="available"))
    _add_if_missing("vehicles", sa.Column("assigned_booking_id", sa.Integer(), nullable=True))


def downgrade():
    for table_name, column_name in (
        ("vehicles", "assigned_booking_id"),
        ("vehicles", "driver_status"),
        ("vehicles", "centre_id"),
        ("bookings", "approved_at"),
        ("bookings", "rejection_reason"),
        ("bookings", "approval_status"),
        ("users", "assigned_centre_id"),
        ("users", "is_active"),
    ):
        inspector = sa.inspect(op.get_bind())
        existing = {item["name"] for item in inspector.get_columns(table_name)}
        if column_name in existing:
            op.drop_column(table_name, column_name)

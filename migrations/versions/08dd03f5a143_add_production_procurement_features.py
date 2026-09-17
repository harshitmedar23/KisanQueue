"""add production procurement features

Revision ID: 08dd03f5a143
Revises: 
Create Date: 2026-09-07 20:04:57.894665

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '08dd03f5a143'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('telegram_chat_id', sa.String(length=32), nullable=True))
    op.add_column('users', sa.Column('telegram_link_code', sa.String(length=10), nullable=True))
    op.create_unique_constraint('uq_users_telegram_chat_id', 'users', ['telegram_chat_id'])
    op.create_unique_constraint('uq_users_telegram_link_code', 'users', ['telegram_link_code'])
    op.add_column('centres', sa.Column('latitude', sa.Float(), nullable=True))
    op.add_column('centres', sa.Column('longitude', sa.Float(), nullable=True))
    op.add_column('bookings', sa.Column('checkin_token', sa.String(length=64), nullable=True))
    op.add_column('bookings', sa.Column('checked_in_at', sa.DateTime(), nullable=True))
    op.create_unique_constraint('uq_bookings_checkin_token', 'bookings', ['checkin_token'])
    with op.batch_alter_table('bookings', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_bookings_checkin_token'), ['checkin_token'], unique=True)
    op.create_table('mandi_prices',
        sa.Column('id', sa.Integer(), nullable=False), sa.Column('crop_type', sa.String(length=80), nullable=False),
        sa.Column('market_name', sa.String(length=120), nullable=False), sa.Column('msp_per_quintal', sa.Float(), nullable=False),
        sa.Column('market_price_per_quintal', sa.Float(), nullable=False), sa.Column('effective_date', sa.Date(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True), sa.PrimaryKeyConstraint('id'))
    op.create_index('ix_mandi_prices_crop_type', 'mandi_prices', ['crop_type'])
    op.create_table('audit_logs',
        sa.Column('id', sa.Integer(), nullable=False), sa.Column('actor_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=80), nullable=False), sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=True), sa.Column('details', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True), sa.ForeignKeyConstraint(['actor_id'], ['users.id']), sa.PrimaryKeyConstraint('id'))
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'])


def downgrade():
    op.drop_index('ix_audit_logs_created_at', table_name='audit_logs')
    op.drop_table('audit_logs')
    op.drop_index('ix_mandi_prices_crop_type', table_name='mandi_prices')
    op.drop_table('mandi_prices')
    with op.batch_alter_table('bookings', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_bookings_checkin_token'))
    op.drop_constraint('uq_bookings_checkin_token', 'bookings', type_='unique')
    op.drop_column('bookings', 'checked_in_at')
    op.drop_column('bookings', 'checkin_token')
    op.drop_column('centres', 'longitude')
    op.drop_column('centres', 'latitude')
    op.drop_constraint('uq_users_telegram_link_code', 'users', type_='unique')
    op.drop_constraint('uq_users_telegram_chat_id', 'users', type_='unique')
    op.drop_column('users', 'telegram_link_code')
    op.drop_column('users', 'telegram_chat_id')

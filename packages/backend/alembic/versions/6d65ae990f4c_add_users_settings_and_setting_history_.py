"""Add users, settings, and setting_history tables

Revision ID: 6d65ae990f4c
Revises:
Create Date: 2025-11-27 22:24:32.868318

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '6d65ae990f4c'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('is_superuser', sa.Boolean(), default=False, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_users_id', 'users', ['id'])
    op.create_index('ix_users_email', 'users', ['email'])

    # Create settings table
    op.create_table(
        'settings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('key', sa.String(255), nullable=False),
        sa.Column('value_type', sa.Enum('STRING', 'INT', 'FLOAT', 'BOOL', 'JSON', name='valuetype'), nullable=False),
        sa.Column('string_value', sa.Text(), nullable=True),
        sa.Column('int_value', sa.Integer(), nullable=True),
        sa.Column('float_value', sa.Float(), nullable=True),
        sa.Column('bool_value', sa.Boolean(), nullable=True),
        sa.Column('json_value', postgresql.JSON(), nullable=True),
        sa.Column('default_value', sa.Text(), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('version', sa.Integer(), default=1, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_settings_id', 'settings', ['id'])
    op.create_index('ix_settings_key', 'settings', ['key'])
    op.create_index('ix_settings_user_id', 'settings', ['user_id'])
    op.create_index('ix_settings_key_user', 'settings', ['key', 'user_id'], unique=True)

    # Create setting_history table
    op.create_table(
        'setting_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('setting_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('old_value', sa.Text(), nullable=False),
        sa.Column('new_value', sa.Text(), nullable=False),
        sa.Column('changed_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('changed_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['setting_id'], ['settings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['changed_by'], ['users.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_setting_history_id', 'setting_history', ['id'])
    op.create_index('ix_setting_history_setting_id', 'setting_history', ['setting_id'])
    op.create_index('ix_setting_history_changed_by', 'setting_history', ['changed_by'])
    op.create_index('ix_setting_history_changed_at', 'setting_history', ['changed_at'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('setting_history')
    op.drop_table('settings')
    op.drop_table('users')

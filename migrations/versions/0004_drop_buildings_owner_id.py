"""drop buildings owner id

Revision ID: 0004_drop_buildings_owner_id
Revises: 0003_data_transform_progress
Create Date: 2026-05-21 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0004_drop_buildings_owner_id"
down_revision: Union[str, Sequence[str], None] = "0003_data_transform_progress"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE buildings DROP COLUMN IF EXISTS owner_id;")


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE buildings
        ADD COLUMN IF NOT EXISTS owner_id UUID REFERENCES users(id) ON DELETE SET NULL;
        """
    )

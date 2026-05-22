"""add data transform progress percent

Revision ID: 0003_data_transform_progress
Revises: 0002_user_buildings
Create Date: 2026-05-21 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0003_data_transform_progress"
down_revision: Union[str, Sequence[str], None] = "0002_user_buildings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE data_transform
        ADD COLUMN IF NOT EXISTS progress_percent INTEGER NOT NULL DEFAULT 0;
        """
    )
    op.execute(
        """
        UPDATE data_transform
        SET progress_percent = CASE
            WHEN status = 'COMPLETED' THEN 100
            WHEN status = 'PROCESSING' THEN 10
            ELSE COALESCE(progress_percent, 0)
        END;
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE data_transform DROP COLUMN IF EXISTS progress_percent;")

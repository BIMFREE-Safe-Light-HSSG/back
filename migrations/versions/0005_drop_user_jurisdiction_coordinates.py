"""drop user jurisdiction coordinates

Revision ID: 0005_drop_jurisdiction_coords
Revises: 0004_drop_buildings_owner_id
Create Date: 2026-05-22 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0005_drop_jurisdiction_coords"
down_revision: Union[str, Sequence[str], None] = "0004_drop_buildings_owner_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS jurisdiction_latitude;")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS jurisdiction_longitude;")


def downgrade() -> None:
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS jurisdiction_latitude DOUBLE PRECISION;"
    )
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS jurisdiction_longitude DOUBLE PRECISION;"
    )

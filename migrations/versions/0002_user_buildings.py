"""add user_buildings relationship

Revision ID: 0002_user_buildings
Revises: 0001_initial_schema
Create Date: 2026-05-21 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0002_user_buildings"
down_revision: Union[str, Sequence[str], None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS user_buildings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            building_id UUID NOT NULL REFERENCES buildings(id) ON DELETE CASCADE,
            role VARCHAR(50) NOT NULL DEFAULT 'OWNER',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (user_id, building_id)
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_user_buildings_user_id
        ON user_buildings(user_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_user_buildings_building_id
        ON user_buildings(building_id);
        """
    )
    op.execute(
        """
        INSERT INTO user_buildings (user_id, building_id, role)
        SELECT owner_id, id, 'OWNER'
        FROM buildings
        WHERE owner_id IS NOT NULL
        ON CONFLICT (user_id, building_id) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS user_buildings;")

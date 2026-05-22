"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-21 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0001_initial_schema"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name VARCHAR(100),
            job VARCHAR(50),
            jurisdiction_code VARCHAR(100),
            jurisdiction_name VARCHAR(255),
            jurisdiction_latitude DOUBLE PRECISION,
            jurisdiction_longitude DOUBLE PRECISION,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS job VARCHAR(50);")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS jurisdiction_code VARCHAR(100);")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS jurisdiction_name VARCHAR(255);")
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS jurisdiction_latitude DOUBLE PRECISION;"
    )
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS jurisdiction_longitude DOUBLE PRECISION;"
    )
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS role;")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS buildings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_id UUID REFERENCES users(id) ON DELETE SET NULL,
            name VARCHAR(255) NOT NULL,
            address TEXT,
            provider VARCHAR(50),
            provider_place_id VARCHAR(255),
            latitude DOUBLE PRECISION,
            longitude DOUBLE PRECISION,
            district_code VARCHAR(100),
            district_name VARCHAR(255),
            region_1depth_name VARCHAR(255),
            region_2depth_name VARCHAR(255),
            region_3depth_name VARCHAR(255),
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    op.execute("ALTER TABLE buildings ADD COLUMN IF NOT EXISTS provider VARCHAR(50);")
    op.execute(
        "ALTER TABLE buildings ADD COLUMN IF NOT EXISTS provider_place_id VARCHAR(255);"
    )
    op.execute(
        "ALTER TABLE buildings ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION;"
    )
    op.execute(
        "ALTER TABLE buildings ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION;"
    )
    op.execute("ALTER TABLE buildings ADD COLUMN IF NOT EXISTS district_code VARCHAR(100);")
    op.execute(
        "ALTER TABLE buildings ADD COLUMN IF NOT EXISTS district_name VARCHAR(255);"
    )
    op.execute(
        "ALTER TABLE buildings ADD COLUMN IF NOT EXISTS region_1depth_name VARCHAR(255);"
    )
    op.execute(
        "ALTER TABLE buildings ADD COLUMN IF NOT EXISTS region_2depth_name VARCHAR(255);"
    )
    op.execute(
        "ALTER TABLE buildings ADD COLUMN IF NOT EXISTS region_3depth_name VARCHAR(255);"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS data_transform (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            building_id UUID REFERENCES buildings(id) ON DELETE CASCADE,
            status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
            scan_file_path TEXT,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS graph_data (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            building_id UUID REFERENCES buildings(id) ON DELETE CASCADE,
            data_transform_id UUID REFERENCES data_transform(id) ON DELETE SET NULL,
            graph_json JSONB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS graph_data;")
    op.execute("DROP TABLE IF EXISTS data_transform;")
    op.execute("DROP TABLE IF EXISTS buildings;")
    op.execute("DROP TABLE IF EXISTS users;")
    op.execute('DROP EXTENSION IF EXISTS "pgcrypto";')

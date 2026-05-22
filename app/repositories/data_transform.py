from typing import Any
from uuid import UUID

from app.core.database import db


async def create_task(
    task_id: UUID,
    building_id: UUID,
    scan_file_path: str,
) -> dict[str, Any] | None:
    return await db.fetch_one(
        """
        INSERT INTO data_transform (
            id, building_id, status, progress_percent, scan_file_path
        )
        VALUES ($1, $2, 'PENDING', 0, $3)
        RETURNING id, building_id, status, progress_percent, error_message, scan_file_path
        """,
        task_id,
        building_id,
        scan_file_path,
    )


async def get_task(task_id: UUID) -> dict[str, Any] | None:
    return await db.fetch_one(
        """
        SELECT
            id,
            building_id,
            status,
            progress_percent,
            error_message,
            scan_file_path
        FROM data_transform
        WHERE id = $1
        """,
        task_id,
    )


async def update_task_status(
    task_id: UUID,
    status: str,
    progress_percent: int,
    error_message: str | None,
) -> dict[str, Any] | None:
    return await db.fetch_one(
        """
        UPDATE data_transform
        SET status = $1,
            progress_percent = $2,
            error_message = $3,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = $4
        RETURNING id, building_id, status, progress_percent, error_message
        """,
        status,
        progress_percent,
        error_message,
        task_id,
    )


async def insert_graph_data(
    building_id: UUID,
    task_id: UUID,
    graph_data_json: str,
) -> dict[str, Any] | None:
    return await db.fetch_one(
        """
        INSERT INTO graph_data (building_id, data_transform_id, graph_json)
        VALUES ($1, $2, $3::jsonb)
        RETURNING id, graph_json::text AS graph_json
        """,
        building_id,
        task_id,
        graph_data_json,
    )

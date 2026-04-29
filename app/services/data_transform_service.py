from typing import Any
from uuid import UUID

from app.core.database import db
from app.schemas.data_transform import (
    TransformTaskCreate,
    TransformTaskStatus,
    TransformTaskUpdateStatus,
)


class DataTransformService:
    async def create_task(self, request: TransformTaskCreate) -> dict[str, Any]:
        task = await db.fetch_one(
            """
            INSERT INTO data_transform_tasks (
                building_id,
                input_data_path,
                status
            )
            VALUES ($1, $2, $3)
            RETURNING
                id,
                building_id,
                status,
                input_data_path,
                error_message,
                created_at,
                updated_at;
            """,
            request.building_id,
            request.input_data_path,
            TransformTaskStatus.PENDING.value,
        )

        return task

    async def get_task(self, task_id: UUID) -> dict[str, Any] | None:
        task = await db.fetch_one(
            """
            SELECT
                id,
                building_id,
                status,
                input_data_path,
                error_message,
                created_at,
                updated_at
            FROM data_transform_tasks
            WHERE id = $1;
            """,
            task_id,
        )

        return task

    async def get_tasks_by_building(
        self,
        building_id: UUID,
    ) -> list[dict[str, Any]]:
        tasks = await db.fetch_all(
            """
            SELECT
                id,
                building_id,
                status,
                input_data_path,
                error_message,
                created_at,
                updated_at
            FROM data_transform_tasks
            WHERE building_id = $1
            ORDER BY created_at DESC;
            """,
            building_id,
        )

        return tasks

    async def update_task_status(
        self,
        task_id: UUID,
        request: TransformTaskUpdateStatus,
    ) -> dict[str, Any] | None:
        task = await db.fetch_one(
            """
            UPDATE data_transform_tasks
            SET status = $1,
                error_message = $2,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = $3
            RETURNING
                id,
                building_id,
                status,
                input_data_path,
                error_message,
                created_at,
                updated_at;
            """,
            request.status.value,
            request.error_message,
            task_id,
        )

        return task

    async def mark_processing(self, task_id: UUID) -> dict[str, Any] | None:
        return await self.update_task_status(
            task_id,
            TransformTaskUpdateStatus(
                status=TransformTaskStatus.PROCESSING,
                error_message=None,
            ),
        )

    async def mark_completed(self, task_id: UUID) -> dict[str, Any] | None:
        return await self.update_task_status(
            task_id,
            TransformTaskUpdateStatus(
                status=TransformTaskStatus.COMPLETED,
                error_message=None,
            ),
        )

    async def mark_failed(
        self,
        task_id: UUID,
        error_message: str,
    ) -> dict[str, Any] | None:
        return await self.update_task_status(
            task_id,
            TransformTaskUpdateStatus(
                status=TransformTaskStatus.FAILED,
                error_message=error_message,
            ),
        )


data_transform_service = DataTransformService()
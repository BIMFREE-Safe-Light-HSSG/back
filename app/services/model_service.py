import os
from typing import Any
from uuid import UUID

import httpx
from dotenv import load_dotenv

from app.schemas.graph import GraphDataCreate
from app.services.data_transform_service import data_transform_service
from app.services.graph_service import graph_service


load_dotenv()


class ModelService:
    def __init__(self) -> None:
        self.model_server_url = os.getenv(
            "MODEL_SERVER_URL",
            " ",
        )

    async def request_graph_transform(
        self,
        task_id: UUID,
    ) -> dict[str, Any]:
        task = await data_transform_service.get_task(task_id)

        if not task:
            raise ValueError("변환 작업을 찾을 수 없습니다.")

        await data_transform_service.mark_processing(task_id)

        try:
            graph_json = await self._call_model_server(
                building_id=task["building_id"],
                input_data_path=task["input_data_path"],
                transform_task_id=task["id"],
            )

            graph = await graph_service.create_graph_data(
                GraphDataCreate(
                    building_id=task["building_id"],
                    transform_task_id=task["id"],
                    graph_json=graph_json,
                )
            )

            await data_transform_service.mark_completed(task_id)

            return {
                "task_id": task_id,
                "status": "COMPLETED",
                "graph": graph,
            }

        except Exception as e:
            await data_transform_service.mark_failed(
                task_id,
                error_message=str(e),
            )

            raise

    async def _call_model_server(
        self,
        building_id: UUID,
        input_data_path: str | None,
        transform_task_id: UUID,
    ) -> dict[str, Any]:
        """
        실제 모델 서버 연동 함수.

        모델 서버가 아직 없다면 일단 mock 데이터를 반환하게 해두고,
        나중에 httpx.post() 부분을 실제 모델 API에 맞춰 수정하면 된다.
        """

        # 임시 mock 반환
        if self.model_server_url == "mock":
            return self._mock_graph_json()

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.model_server_url}/transform",
                json={
                    "building_id": str(building_id),
                    "input_data_path": input_data_path,
                    "transform_task_id": str(transform_task_id),
                },
            )

            response.raise_for_status()

            data = response.json()

            return data["graph_json"]

    def _mock_graph_json(self) -> dict[str, Any]:
        return {
            "nodes": [
                {
                    "id": "building_001",
                    "type": "Building",
                    "label": "Sample Building",
                    "properties": {},
                },
                {
                    "id": "floor_1",
                    "type": "Floor",
                    "label": "1F",
                    "properties": {},
                },
                {
                    "id": "room_101",
                    "type": "Room",
                    "label": "Room 101",
                    "properties": {},
                },
                {
                    "id": "door_101",
                    "type": "Door",
                    "label": "Door 101",
                    "properties": {},
                },
            ],
            "edges": [
                {
                    "source": "building_001",
                    "target": "floor_1",
                    "relation": "contains",
                    "properties": {},
                },
                {
                    "source": "floor_1",
                    "target": "room_101",
                    "relation": "contains",
                    "properties": {},
                },
                {
                    "source": "room_101",
                    "target": "door_101",
                    "relation": "has_door",
                    "properties": {},
                },
            ],
        }


model_service = ModelService()
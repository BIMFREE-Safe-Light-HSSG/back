from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse


router = APIRouter(prefix="/dev", tags=["dev"])


@router.get("/upload-test", include_in_schema=False)
async def upload_test_page() -> FileResponse:
    html_path = Path(__file__).with_name("upload_test.html")
    return FileResponse(html_path, media_type="text/html")

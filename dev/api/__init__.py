"""Development-only API routers."""

from dev.api.alert import router as alert_router
from dev.api.rfid_tag import router as rfid_tag_router
from dev.api.scene_graphs import router as scene_graphs_router


routers = [scene_graphs_router, alert_router, rfid_tag_router]

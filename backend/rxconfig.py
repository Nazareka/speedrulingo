from __future__ import annotations

import os
from pathlib import Path
import sys

import reflex as rx
from reflex_base.constants import StateManagerMode
from reflex_base.plugins.sitemap import SitemapPlugin

BACKEND_ROOT = Path(__file__).resolve().parent
SRC_ROOT = BACKEND_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

config = rx.Config(
    app_name="course_builder_ui",
    app_module_import="course_builder.ui.app",
    api_url="http://localhost:8001",
    deploy_url="http://localhost:3001",
    backend_port=8001,
    frontend_port=3002,
    state_manager_mode=StateManagerMode.REDIS,
    db_url=None,
    async_db_url=None,
    redis_url=os.environ.get("SPEEDRULINGO_REDIS_URL"),
    cors_allowed_origins=[
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    disable_plugins=[SitemapPlugin],
)

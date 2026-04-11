from __future__ import annotations

from threading import Lock

from dbos import DBOS, DBOSConfig

from settings import get_settings

_LAUNCH_LOCK = Lock()
_DBOS_INITIALIZED = False


def build_dbos_config() -> DBOSConfig:
    settings = get_settings()
    return {
        "name": "speedrulingo-course-builder",
        "system_database_url": settings.dbos_system_database_url,
    }


def launch_dbos() -> None:
    global _DBOS_INITIALIZED
    with _LAUNCH_LOCK:
        if _DBOS_INITIALIZED:
            return
        DBOS(config=build_dbos_config())
        DBOS.launch()
        _DBOS_INITIALIZED = True


def cancel_dbos_workflow(*, workflow_id: str) -> None:
    launch_dbos()
    DBOS.cancel_workflow(workflow_id)


async def cancel_dbos_workflow_async(*, workflow_id: str) -> None:
    launch_dbos()
    await DBOS.cancel_workflow_async(workflow_id)

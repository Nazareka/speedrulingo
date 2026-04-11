from __future__ import annotations

from functools import lru_cache
import json
import logging
from typing import TypedDict

from redis import Redis
from redis.exceptions import RedisError

from settings import get_settings

LOGGER = logging.getLogger(__name__)
BUILD_RUN_EVENTS_CHANNEL = "course_builder.build_run_events"


class BuildRunEvent(TypedDict):
    event_type: str
    build_run_id: str
    parent_build_run_id: str | None


def _get_redis_url() -> str | None:
    return get_settings().redis_url


@lru_cache(maxsize=1)
def _get_redis_client() -> Redis | None:
    redis_url = _get_redis_url()
    if redis_url is None:
        return None
    return Redis.from_url(redis_url, decode_responses=True)


def publish_build_run_event(
    *,
    event_type: str,
    build_run_id: str,
    parent_build_run_id: str | None,
) -> None:
    redis_client = _get_redis_client()
    if redis_client is None:
        return
    payload: BuildRunEvent = {
        "event_type": event_type,
        "build_run_id": build_run_id,
        "parent_build_run_id": parent_build_run_id,
    }
    try:
        redis_client.publish(BUILD_RUN_EVENTS_CHANNEL, json.dumps(payload))
    except RedisError:
        LOGGER.exception("Failed to publish build-run event")


def related_build_run_ids(event: BuildRunEvent) -> set[str]:
    related_ids = {event["build_run_id"]}
    parent_build_run_id = event.get("parent_build_run_id")
    if parent_build_run_id:
        related_ids.add(parent_build_run_id)
    return related_ids

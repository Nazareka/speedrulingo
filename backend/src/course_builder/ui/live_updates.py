from __future__ import annotations

import asyncio
from collections import defaultdict
import json
import logging
from threading import Lock
from typing import cast

from redis.asyncio import Redis
from redis.exceptions import RedisError
import reflex as rx

from course_builder.build_runs.live_updates import BUILD_RUN_EVENTS_CHANNEL, BuildRunEvent, related_build_run_ids
from course_builder.ui.reflex_compat import (
    get_course_builder_state_token,
    get_reflex_app,
    has_live_state_owner,
)
from course_builder.ui.state import CourseBuilderUIState, _ensure_ui_runtime, build_dashboard_snapshot
from settings import get_settings

LOGGER = logging.getLogger(__name__)


class BuildRunSubscriptionRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        self._dashboard_tokens: set[str] = set()
        self._token_to_build_run_id: dict[str, str] = {}
        self._build_run_id_to_tokens: dict[str, set[str]] = defaultdict(set)

    def register(self, *, client_token: str, build_run_id: str | None) -> None:
        if not client_token:
            return
        state_token = get_course_builder_state_token(client_token=client_token)
        with self._lock:
            self._dashboard_tokens.add(state_token)
            previous_build_run_id = self._token_to_build_run_id.get(state_token)
            if previous_build_run_id is not None and previous_build_run_id != build_run_id:
                previous_tokens = self._build_run_id_to_tokens.get(previous_build_run_id)
                if previous_tokens is not None:
                    previous_tokens.discard(state_token)
                    if not previous_tokens:
                        self._build_run_id_to_tokens.pop(previous_build_run_id, None)
            if build_run_id:
                self._token_to_build_run_id[state_token] = build_run_id
                self._build_run_id_to_tokens[build_run_id].add(state_token)
            else:
                self._token_to_build_run_id.pop(state_token, None)

    def unregister(self, *, state_token: str) -> None:
        if not state_token:
            return
        with self._lock:
            self._dashboard_tokens.discard(state_token)
            previous_build_run_id = self._token_to_build_run_id.pop(state_token, None)
            if previous_build_run_id is None:
                return
            tokens = self._build_run_id_to_tokens.get(previous_build_run_id)
            if tokens is None:
                return
            tokens.discard(state_token)
            if not tokens:
                self._build_run_id_to_tokens.pop(previous_build_run_id, None)

    def subscribed_tokens_for_event(self, event: BuildRunEvent) -> set[str]:
        with self._lock:
            tokens = set(self._dashboard_tokens)
            for build_run_id in related_build_run_ids(event):
                tokens.update(self._build_run_id_to_tokens.get(build_run_id, set()))
            return tokens


BUILD_RUN_SUBSCRIPTIONS = BuildRunSubscriptionRegistry()


async def run_build_run_event_listener() -> None:
    _ensure_ui_runtime()
    redis_url = get_settings().redis_url
    if redis_url is None:
        LOGGER.warning("Redis URL is not configured; live UI updates are disabled")
        return

    backoff_seconds = 1.0
    while True:
        redis = Redis.from_url(redis_url, decode_responses=True)
        pubsub = redis.pubsub()
        try:
            await pubsub.subscribe(BUILD_RUN_EVENTS_CHANNEL)
            backoff_seconds = 1.0
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message is None:
                    await asyncio.sleep(0.1)
                    continue
                data = message.get("data")
                if not isinstance(data, str):
                    continue
                try:
                    raw_event = json.loads(data)
                    if not isinstance(raw_event, dict):
                        raise ValueError("Build-run event payload must be a mapping")
                    event = cast(BuildRunEvent, raw_event)
                except (TypeError, ValueError):
                    LOGGER.exception("Failed to decode build-run event payload")
                    continue
                await _refresh_subscribed_clients(app=get_reflex_app(), event=event)
        except asyncio.CancelledError:
            raise
        except RedisError:
            LOGGER.exception("Redis Pub/Sub listener failed; retrying in %.1fs", backoff_seconds)
            await asyncio.sleep(backoff_seconds)
            backoff_seconds = min(backoff_seconds * 2, 30.0)
        finally:
            try:
                await pubsub.unsubscribe(BUILD_RUN_EVENTS_CHANNEL)
            except RedisError:
                LOGGER.exception("Failed to unsubscribe Redis Pub/Sub listener cleanly")
            try:
                await pubsub.aclose()  # type: ignore[no-untyped-call]  # redis-py pubsub close is async at runtime but currently untyped.
            except RedisError:
                LOGGER.exception("Failed to close Redis Pub/Sub listener cleanly")
            try:
                await redis.aclose()
            except RedisError:
                LOGGER.exception("Failed to close Redis client cleanly")


async def _refresh_subscribed_clients(*, app: rx.App, event: BuildRunEvent) -> None:
    for state_token in BUILD_RUN_SUBSCRIPTIONS.subscribed_tokens_for_event(event):
        if not has_live_state_owner(app=app, state_token=state_token):
            BUILD_RUN_SUBSCRIPTIONS.unregister(state_token=state_token)
            continue
        try:
            async with app.modify_state(state_token) as state:
                ui_state = await state.get_state(CourseBuilderUIState)
                config_path = ui_state.config_path
                current_section_code = ui_state.section_code
                all_sections = ui_state.all_sections
                selected_run_id = ui_state.selected_run_id
                launched_workflow_id = ui_state.launched_workflow_id
            snapshot = build_dashboard_snapshot(
                config_path=config_path,
                current_section_code=current_section_code,
                all_sections=all_sections,
                selected_run_id=selected_run_id,
                launched_workflow_id=launched_workflow_id,
            )
            async with app.modify_state(state_token) as state:
                ui_state = await state.get_state(CourseBuilderUIState)
                ui_state.refresh_for_live_update(snapshot)
        except Exception:
            BUILD_RUN_SUBSCRIPTIONS.unregister(state_token=state_token)
            LOGGER.exception("Failed to push live update to subscribed Reflex client")

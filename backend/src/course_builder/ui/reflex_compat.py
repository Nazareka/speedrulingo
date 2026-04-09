from __future__ import annotations

from collections.abc import Callable
from typing import cast

import reflex as rx
import reflex.app as reflex_app
from reflex.state import _substate_key
from reflex.utils.prerequisites import get_and_validate_app

from course_builder.ui.state import CourseBuilderUIState

# Reflex does not currently expose stable public helpers for computing the Redis
# substate token or resolving the concrete rx.App instance inside lifespan
# tasks. Keep those private-framework touchpoints isolated here so upgrades only
# need one compatibility review.


def get_reflex_app() -> rx.App:
    # Lifespan tasks receive Starlette's app object, but live updates need the
    # concrete Reflex app to call `modify_state(...)` out-of-band.
    return get_and_validate_app().app


def get_course_builder_state_token(*, client_token: str) -> str:
    # Reflex Redis state is keyed by a substate token, not the raw browser tab
    # token. Centralize that conversion here so subscriptions use the exact key
    # shape `modify_state(...)` expects.
    return _substate_key(client_token, CourseBuilderUIState)


def has_live_state_owner(*, app: rx.App, state_token: str) -> bool:
    # Reflex logs noisy "lost and found" warnings if we try to push a delta to a
    # token that no longer has a live socket on this process. Check ownership
    # first so dead/stale subscriptions can be pruned quietly.
    event_namespace = app.event_namespace
    if event_namespace is None:
        return False
    # Access the module dict directly so mypy does not type-check this private
    # Reflex helper as part of the public module surface.
    split_substate_key_obj = vars(reflex_app)["_split_substate_key"]
    split_substate_key = cast(
        Callable[[str], tuple[str, str]],
        split_substate_key_obj,
    )
    client_token, _ = split_substate_key(state_token)
    socket_record = event_namespace._token_manager.token_to_socket.get(client_token)
    return (
        socket_record is not None
        and socket_record.instance_id == event_namespace._token_manager.instance_id
    )

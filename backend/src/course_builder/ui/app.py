from __future__ import annotations

import reflex as rx

from course_builder.ui.components import dashboard_page
from course_builder.ui.live_updates import run_build_run_event_listener
from course_builder.ui.state import CourseBuilderUIState

app = rx.App(theme=rx.theme(appearance="dark", accent_color="grass"))
app.register_lifespan_task(run_build_run_event_listener)
app.add_page(
    dashboard_page,
    route="/",
    title="Course Builder Console",
    on_load=CourseBuilderUIState.load_dashboard,
)

from __future__ import annotations

from typing import Any

import reflex as rx

from course_builder.ui.state import CourseBuilderUIState

# Keep Reflex component composition in this module. It is the UI presentation
# boundary, so pages and reusable Reflex components should live here rather than
# being spread across state/runtime modules.


def _display_value(value: Any) -> Any:
    return rx.cond((value == None) | (value == ""), "—", value)  # noqa: E711  # Reflex vars overload `==` into runtime expressions.


def _status_chip(status: Any) -> rx.Component:
    return rx.badge(
        status,
        color_scheme=rx.match(
            status,
            ("completed", "grass"),
            ("running", "blue"),
            ("failed", "tomato"),
            ("queued", "amber"),
            ("cancelled", "gray"),
            "gray",
        ),
        variant="soft",
    )


def _labeled_value(label: str, value: Any) -> rx.Component:
    return rx.vstack(
        rx.text(label, size="1", color="cyan"),
        rx.text(
            _display_value(value),
            size="3",
            weight="medium",
            width="100%",
            white_space="normal",
            word_break="break-word",
        ),
        align="start",
        spacing="1",
        width="100%",
        min_width="0",
    )


def _run_row(run: Any) -> rx.Component:
    is_selected = CourseBuilderUIState.selected_run_id == run["id"]
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.text(run["scope_kind"], weight="bold"),
                rx.cond(run["section_code"], rx.text(_display_value(run["section_code"]), color="teal"), rx.fragment()),
                rx.spacer(),
                _status_chip(run["status"]),
                width="100%",
                align="center",
            ),
            rx.hstack(
                rx.text(f"build #{run['build_version']}"),
                rx.text(run["config_path"], color="cyan"),
                width="100%",
                justify="between",
            ),
            rx.text(
                f"{run['completed_stage_count']} / {run['total_stage_count']} stages",
                size="2",
                color="amber",
            ),
            align="start",
            width="100%",
            spacing="2",
        ),
        on_click=lambda: CourseBuilderUIState.select_run(run["id"]),
        width="100%",
        padding="1rem",
        background=rx.cond(
            is_selected,
            "linear-gradient(135deg, rgba(20, 83, 45, 0.34), rgba(15, 23, 42, 0.9))",
            "rgba(15, 23, 42, 0.72)",
        ),
        border=rx.cond(
            is_selected,
            "1px solid rgba(134, 239, 172, 0.85)",
            "1px solid rgba(134, 239, 172, 0.28)",
        ),
        box_shadow=rx.cond(
            is_selected,
            "inset 0 0 0 1px rgba(187, 247, 208, 0.24), 0 0 0 1px rgba(22, 163, 74, 0.18)",
            "none",
        ),
        border_radius="14px",
        cursor="pointer",
        transition="background 120ms ease, border-color 120ms ease, transform 120ms ease",
        _hover=rx.cond(
            is_selected,
            {
                "background": "linear-gradient(135deg, rgba(20, 83, 45, 0.34), rgba(15, 23, 42, 0.9))",
                "border_color": "rgba(134, 239, 172, 0.85)",
                "box_shadow": "inset 0 0 0 1px rgba(187, 247, 208, 0.24), 0 0 0 1px rgba(22, 163, 74, 0.18)",
                "transform": "translateY(-1px)",
            },
            {
                "background": "rgba(22, 33, 54, 0.9)",
                "border_color": "rgba(134, 239, 172, 0.52)",
                "transform": "translateY(-1px)",
            },
        ),
    )


def _stage_row(stage_run: Any) -> rx.Component:
    return rx.hstack(
        rx.text(f"{stage_run['stage_index']}.", width="3rem", color="cyan"),
        rx.text(
            stage_run["stage_name"],
            width="18rem",
            weight="medium",
            white_space="normal",
            word_break="break-word",
        ),
        _status_chip(stage_run["status"]),
        rx.spacer(),
        rx.text(
            _display_value(stage_run["started_at"]),
            color="teal",
            size="1",
            text_align="right",
            white_space="normal",
            word_break="break-word",
            max_width="12rem",
        ),
        width="100%",
        align="center",
        padding_y="0.4rem",
        border_bottom="1px solid var(--gray-4)",
        min_width="0",
        wrap="wrap",
    )


def _child_run_row(run: Any) -> rx.Component:
    return rx.hstack(
        rx.text(run["section_code"], weight="bold", width="8rem"),
        _status_chip(run["status"]),
        rx.text(f"{run['completed_stage_count']} / {run['total_stage_count']}", color="amber", size="1", width="8rem"),
        rx.spacer(),
        rx.text(_display_value(run["current_stage_name"]), color="teal"),
        width="100%",
        align="center",
        padding_y="0.4rem",
        border_bottom="1px solid var(--gray-4)",
    )


def _log_view_toggle_button(label: str, mode: str) -> rx.Component:
    is_active = CourseBuilderUIState.log_view_mode == mode
    return rx.button(
        label,
        on_click=lambda: CourseBuilderUIState.set_log_view_mode(mode),
        variant=rx.cond(is_active, "solid", "soft"),
        color_scheme=rx.cond(is_active, "grass", "gray"),
        size="1",
    )


def _raw_log_view() -> rx.Component:
    return rx.box(
        rx.text(
            CourseBuilderUIState.log_text,
            white_space="pre-wrap",
            font_family="'IBM Plex Mono', monospace",
            size="2",
            width="100%",
        ),
        width="100%",
        padding="1rem",
        border="1px solid rgba(148, 163, 184, 0.16)",
        border_radius="14px",
        background="rgba(2, 6, 23, 0.48)",
    )


def _pretty_log_row(event: Any) -> rx.Component:
    return rx.match(
        event["kind"],
        (
            "section",
            rx.text(
                event["label"],
                size="4",
                weight="bold",
                color="lime",
                margin_top="0.75rem",
            ),
        ),
        (
            "stage",
            rx.box(
                rx.text(
                    event["label"],
                    size="3",
                    weight="medium",
                    color="lime",
                ),
                margin_top="0.5rem",
                padding_left="2.1rem",
                border_left="2px solid rgba(34, 197, 94, 0.28)",
                width="100%",
                min_width="0",
            ),
        ),
        rx.vstack(
            rx.grid(
                rx.box(
                    rx.cond(
                        event["show_timestamp"],
                        rx.text(
                            _display_value(event["timestamp"]),
                            color="cyan",
                            size="1",
                        ),
                        rx.fragment(),
                    ),
                    width="11rem",
                    min_width="11rem",
                ),
                rx.hstack(
                    rx.text("•", color="teal", flex_shrink="0"),
                    rx.text(
                        event["message"],
                        size="2",
                        white_space="normal",
                        word_break="break-word",
                    ),
                    spacing="3",
                    align="start",
                    width="100%",
                    min_width="0",
                ),
                rx.badge(
                    event["level"],
                    variant="soft",
                    color_scheme=rx.match(
                        event["level"],
                        ("ERROR", "tomato"),
                        ("WARNING", "amber"),
                        ("INFO", "blue"),
                        ("DEBUG", "gray"),
                        "gray",
                    ),
                    flex_shrink="0",
                ),
                columns="11rem 1fr auto",
                width="100%",
                spacing="3",
                min_width="0",
                align="start",
            ),
            width="100%",
            spacing="1",
            padding_left="2rem",
            min_width="0",
            align="start",
        ),
    )


def _pretty_log_view() -> rx.Component:
    return rx.vstack(
        rx.foreach(CourseBuilderUIState.pretty_log_rows, _pretty_log_row),
        width="100%",
        spacing="3",
        align="start",
        min_width="0",
    )


def build_form() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.heading("Start Build", size="5"),
            rx.hstack(
                rx.box(
                    rx.text("Config path", size="1", color="cyan"),
                    rx.input(
                        value=CourseBuilderUIState.config_path,
                        on_change=CourseBuilderUIState.set_config_path_value,
                        width="100%",
                    ),
                    width="24rem",
                ),
                rx.box(
                    rx.text("Build version", size="1", color="cyan"),
                    rx.input(
                        value=CourseBuilderUIState.build_version_input,
                        on_change=CourseBuilderUIState.set_build_version_input_value,
                        width="10rem",
                    ),
                ),
                rx.box(
                    rx.text("Section code", size="1", color="cyan"),
                    rx.select(
                        CourseBuilderUIState.available_section_codes,
                        value=CourseBuilderUIState.section_code,
                        on_change=CourseBuilderUIState.set_section_code_value,
                        disabled=CourseBuilderUIState.all_sections,
                        placeholder="Select section",
                        width="10rem",
                    ),
                ),
                spacing="4",
                wrap="wrap",
                width="100%",
            ),
            rx.hstack(
                rx.hstack(
                    rx.switch(
                        checked=CourseBuilderUIState.all_sections,
                        on_change=CourseBuilderUIState.toggle_all_sections,
                    ),
                    rx.text("Run all sections"),
                    spacing="2",
                ),
                rx.hstack(
                    rx.switch(
                        checked=CourseBuilderUIState.all_stages,
                        on_change=CourseBuilderUIState.set_all_stages_value,
                    ),
                    rx.text("Run all remaining stages"),
                    spacing="2",
                ),
                rx.spacer(),
                rx.button("Refresh", on_click=CourseBuilderUIState.refresh_now, variant="soft"),
                rx.button("Start build", on_click=CourseBuilderUIState.start_build, color_scheme="grass"),
                width="100%",
                align="center",
            ),
            rx.cond(
                CourseBuilderUIState.launch_message != "",
                rx.text(CourseBuilderUIState.launch_message, color="lime"),
                rx.fragment(),
            ),
            rx.cond(
                CourseBuilderUIState.sentence_audio_message != "",
                rx.text(CourseBuilderUIState.sentence_audio_message, color="lime"),
                rx.fragment(),
            ),
            rx.cond(
                CourseBuilderUIState.error_message != "",
                rx.text(CourseBuilderUIState.error_message, color="red"),
                rx.fragment(),
            ),
            width="100%",
            spacing="4",
            align="start",
        ),
        width="100%",
        padding="1.25rem",
        background="linear-gradient(135deg, rgba(11,30,45,0.96), rgba(26,46,61,0.92))",
        border="1px solid rgba(148, 163, 184, 0.22)",
        border_radius="18px",
    )


def build_runs_sidebar() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.heading("Recent Runs", size="5"),
                rx.spacer(),
                rx.text(CourseBuilderUIState.build_runs_count, color="amber", size="1"),
                width="100%",
            ),
            rx.foreach(CourseBuilderUIState.build_runs, _run_row),
            width="100%",
            spacing="3",
            align="start",
        ),
        width="28rem",
        min_width="28rem",
    )


def build_run_detail() -> rx.Component:
    selected_run = CourseBuilderUIState.selected_run
    return rx.box(
        rx.vstack(
            rx.cond(
                CourseBuilderUIState.has_selected_run,
                rx.vstack(
                    rx.box(
                        rx.hstack(
                            rx.vstack(
                                rx.heading("Run Detail", size="6"),
                                rx.text(
                                    selected_run["id"],
                                    color="cyan",
                                    size="1",
                                    width="100%",
                                    white_space="normal",
                                    word_break="break-all",
                                ),
                                align="start",
                                spacing="1",
                                min_width="0",
                                flex="1",
                            ),
                            rx.spacer(),
                            rx.hstack(
                                rx.button(
                                    "Generate hiragana audio",
                                    on_click=CourseBuilderUIState.start_hiragana_audio_generation,
                                    color_scheme="grass",
                                    variant="soft",
                                ),
                                rx.button(
                                    "Generate katakana audio",
                                    on_click=CourseBuilderUIState.start_katakana_audio_generation,
                                    color_scheme="grass",
                                    variant="soft",
                                ),
                                rx.cond(
                                    CourseBuilderUIState.can_generate_selected_run_audio,
                                    rx.button(
                                        "Generate sentence audio",
                                        on_click=CourseBuilderUIState.start_sentence_audio_generation,
                                        color_scheme="grass",
                                        variant="soft",
                                    ),
                                    rx.fragment(),
                                ),
                                rx.cond(
                                    CourseBuilderUIState.can_generate_selected_run_word_audio,
                                    rx.button(
                                        "Generate word audio",
                                        on_click=CourseBuilderUIState.start_word_audio_generation,
                                        color_scheme="grass",
                                        variant="soft",
                                    ),
                                    rx.fragment(),
                                ),
                                rx.cond(
                                    CourseBuilderUIState.can_cancel_selected_run,
                                    rx.button(
                                        "Cancel run",
                                        on_click=CourseBuilderUIState.cancel_selected_run,
                                        color_scheme="tomato",
                                        variant="solid",
                                    ),
                                    rx.fragment(),
                                ),
                                _status_chip(selected_run["status"]),
                                spacing="3",
                                align="center",
                                flex_shrink="0",
                            ),
                            width="100%",
                            align="center",
                            min_width="0",
                            wrap="wrap",
                        ),
                        position="sticky",
                        top="0",
                        z_index="10",
                        width="100%",
                        padding_bottom="0.75rem",
                        background="linear-gradient(180deg, rgba(15, 23, 42, 0.98) 0%, rgba(15, 23, 42, 0.9) 78%, rgba(15, 23, 42, 0.0) 100%)",
                    ),
                    rx.grid(
                        _labeled_value("Scope", selected_run["scope_kind"]),
                        _labeled_value("Section", selected_run["section_code"]),
                        _labeled_value("Build version", selected_run["build_version"]),
                        _labeled_value("Workflow ID", selected_run["workflow_id"]),
                        _labeled_value("Current stage", selected_run["current_stage_name"]),
                        _labeled_value("Course version", selected_run["course_version_id"]),
                        columns="3",
                        spacing="4",
                        width="100%",
                        min_width="0",
                    ),
                    rx.box(
                        rx.text(
                            f"{selected_run['completed_stage_count']} / {selected_run['total_stage_count']} completed",
                            size="3",
                            margin_bottom="0.5rem",
                        ),
                        width="100%",
                    ),
                    rx.cond(
                        selected_run["scope_kind"] == "all_sections",
                        rx.callout(
                            "This parent run shows aggregate build progress. Detailed stage execution lives on the child section runs below, and the log panel includes child section events.",
                            icon="info",
                            color_scheme="blue",
                            width="100%",
                        ),
                        rx.fragment(),
                    ),
                    rx.cond(
                        CourseBuilderUIState.child_section_runs_count > 0,
                        rx.box(
                            rx.heading("Section Runs", size="4", margin_bottom="0.75rem"),
                            rx.foreach(CourseBuilderUIState.child_section_runs, _child_run_row),
                            width="100%",
                        ),
                        rx.fragment(),
                    ),
                    rx.cond(
                        (selected_run["scope_kind"] != "all_sections")
                        | (CourseBuilderUIState.child_section_runs_count == 0),
                        rx.box(
                            rx.heading("Stage Runs", size="4", margin_bottom="0.75rem"),
                            rx.foreach(CourseBuilderUIState.stage_runs, _stage_row),
                            width="100%",
                        ),
                        rx.fragment(),
                    ),
                    rx.box(
                        rx.hstack(
                            rx.heading(
                                rx.cond(
                                    selected_run["scope_kind"] == "all_sections",
                                    "Live Logs (Parent + Child Sections)",
                                    "Live Logs",
                                ),
                                size="4",
                            ),
                            rx.spacer(),
                            rx.hstack(
                                _log_view_toggle_button("Pretty", "pretty"),
                                _log_view_toggle_button("Raw", "raw"),
                                spacing="2",
                            ),
                            rx.text(CourseBuilderUIState.log_events_count, color="amber", size="1"),
                            width="100%",
                            wrap="wrap",
                            spacing="3",
                        ),
                        rx.cond(
                            CourseBuilderUIState.log_view_mode == "raw",
                            _raw_log_view(),
                            _pretty_log_view(),
                        ),
                        width="100%",
                        min_width="0",
                    ),
                    width="100%",
                    spacing="5",
                    align="start",
                    min_width="0",
                ),
                rx.text("No build run selected.", color="cyan"),
            ),
            width="100%",
            spacing="4",
            align="start",
            min_width="0",
        ),
        flex="1",
        min_width="0",
        width="100%",
        padding="1.25rem",
        border="1px solid var(--gray-5)",
        border_radius="18px",
        background="rgba(15, 23, 42, 0.72)",
    )


def dashboard_page() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.vstack(
                rx.text("Speedrulingo Course Builder", size="2", color="lime"),
                rx.heading("DBOS Run Console", size="8"),
                rx.text(
                    "Start DBOS-backed course builds, inspect live progress, and read persisted operator logs.",
                    size="3",
                    color="cyan",
                ),
                spacing="2",
                align="start",
                width="100%",
            ),
            build_form(),
            rx.hstack(
                build_runs_sidebar(),
                build_run_detail(),
                width="100%",
                align="start",
                spacing="5",
                min_width="0",
            ),
            width="100%",
            max_width="1800px",
            margin_x="auto",
            padding="2rem",
            spacing="5",
            align="start",
        ),
        min_height="100vh",
        width="100%",
        background=(
            "radial-gradient(circle at top left, rgba(34,197,94,0.12), transparent 28%), "
            "linear-gradient(180deg, #07131d 0%, #0f172a 55%, #081019 100%)"
        ),
    )

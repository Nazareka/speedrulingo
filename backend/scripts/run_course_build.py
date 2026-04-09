from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

from dbos import DBOS

from app_logging import configure_logging
from course_builder.runtime import build_all_sections_workflow, build_request, build_section_workflow, launch_dbos


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run course builder workflows through DBOS.")
    parser.add_argument("--config", type=Path, required=True, help="Path to the course build config directory.")
    parser.add_argument("--section-code", type=str, required=False, help="Exact section code to build.")
    parser.add_argument("--build-version", type=int, required=True, help="Run number for this logical course build.")
    parser.add_argument("--all-stages", action="store_true", help="Run all remaining stages for the requested scope.")
    parser.add_argument("--all-sections", action="store_true", help="Run all declared sections in order.")
    parser.add_argument(
        "--background",
        action="store_true",
        help="Start the DBOS workflow in the background and print the workflow ID without waiting.",
    )
    return parser


def main() -> int:
    configure_logging()
    launch_dbos()
    args = build_parser().parse_args()
    request = build_request(
        config=args.config,
        build_version=args.build_version,
        section_code=args.section_code,
        all_stages=args.all_stages,
        all_sections=args.all_sections,
    )
    workflow_handle: Any
    if request.all_sections:
        workflow_handle = DBOS.start_workflow(
            build_all_sections_workflow,
            str(request.config),
            request.build_version,
            request.all_stages,
        )
    else:
        workflow_handle = DBOS.start_workflow(
            build_section_workflow,
            str(request.config),
            request.build_version,
            request.section_code or "",
            request.all_stages,
        )
    sys.stdout.write(f"workflow_id={workflow_handle.get_workflow_id()}\n")
    if args.background:
        return 0
    summary = workflow_handle.get_result()
    sys.stdout.write(f"{summary}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

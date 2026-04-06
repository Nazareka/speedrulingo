from __future__ import annotations

import argparse
from pathlib import Path
import sys

from app_logging import configure_logging
from course_builder.prefect.flows import build_all_sections_flow, build_request, build_section_flow


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run course builder flows through Prefect.")
    parser.add_argument("--config", type=Path, required=True, help="Path to the course build config directory.")
    parser.add_argument("--section-code", type=str, required=False, help="Exact section code to build.")
    parser.add_argument("--build-version", type=int, required=True, help="Run number for this logical course build.")
    parser.add_argument("--all-stages", action="store_true", help="Run all remaining stages for the requested scope.")
    parser.add_argument("--all-sections", action="store_true", help="Run all declared sections in order.")
    return parser


def main() -> int:
    configure_logging()
    args = build_parser().parse_args()
    request = build_request(
        config=args.config,
        build_version=args.build_version,
        section_code=args.section_code,
        all_stages=args.all_stages,
        all_sections=args.all_sections,
    )
    summary = (
        build_all_sections_flow(
            config=str(request.config),
            build_version=request.build_version,
            all_stages=request.all_stages,
        )
        if request.all_sections
        else build_section_flow(
            config=str(request.config),
            build_version=request.build_version,
            section_code=request.section_code or "",
            all_stages=request.all_stages,
        )
    )
    sys.stdout.write(f"{summary}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

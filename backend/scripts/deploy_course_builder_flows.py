from __future__ import annotations

import argparse
import asyncio
import inspect
from typing import cast

from prefect import deploy
from prefect.client.orchestration import get_client
from prefect.client.schemas.actions import WorkPoolCreate
from prefect.deployments.runner import RunnerDeployment
from prefect.exceptions import ObjectNotFound
from prefect.types.entrypoint import EntrypointType

from course_builder.prefect.flows import build_all_sections_flow, build_section_flow

WORK_POOL_NAME = "speedrulingo-builder"
WORK_POOL_TYPE = "process"


def _resolve_deployment(value: RunnerDeployment | object) -> RunnerDeployment:
    if inspect.isawaitable(value):
        msg = "Synchronous deploy bootstrap received an awaitable deployment"
        raise RuntimeError(msg)
    return cast(RunnerDeployment, value)


async def ensure_work_pool() -> None:
    async with get_client() as client:
        try:
            await client.read_work_pool(WORK_POOL_NAME)
        except ObjectNotFound:
            await client.create_work_pool(
                WorkPoolCreate(
                    name=WORK_POOL_NAME,
                    type=WORK_POOL_TYPE,
                    description="Local Prefect process pool for Speedrulingo course builder flows.",
                )
            )


def deploy_flows() -> None:
    asyncio.run(ensure_work_pool())
    section_deployment = _resolve_deployment(
        build_section_flow.to_deployment(
        name="section-build",
        parameters={
            "config": "/app/config/en-ja-v1",
            "build_version": 1,
            "section_code": "PRE_A1",
            "all_stages": True,
        },
        description="Build one section of a Speedrulingo course through all remaining stages.",
        tags=["course-builder"],
        entrypoint_type=EntrypointType.MODULE_PATH,
    ))
    all_sections_deployment = _resolve_deployment(
        build_all_sections_flow.to_deployment(
        name="all-sections-build",
        parameters={
            "config": "/app/config/en-ja-v1",
            "build_version": 1,
            "all_stages": True,
        },
        description="Build all declared sections of a Speedrulingo course in order.",
        tags=["course-builder"],
        entrypoint_type=EntrypointType.MODULE_PATH,
    ))
    deploy(
        section_deployment,
        all_sections_deployment,
        work_pool_name=WORK_POOL_NAME,
        build=False,
        push=False,
        print_next_steps_message=False,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bootstrap Prefect work pool and deployments for course builder flows.")
    parser.add_argument(
        "--ensure-work-pool-only",
        action="store_true",
        help="Create the work pool if needed, but do not register deployments.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.ensure_work_pool_only:
        asyncio.run(ensure_work_pool())
        return 0
    deploy_flows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

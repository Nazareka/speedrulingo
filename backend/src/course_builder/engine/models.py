from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Protocol

from sqlalchemy.orm import Session

from course_builder.config import CourseBuildConfig
from domain.content.models import CourseVersion


class BuildStep(Protocol):
    name: str

    def run(self, *, db: Session, context: BuildContext) -> Any: ...


@dataclass(slots=True)
class BuildContext:
    config: CourseBuildConfig
    config_hash: str
    course_version: CourseVersion
    course_version_id: str
    section_code: str


def compute_config_hash(config: CourseBuildConfig) -> str:
    payload = json.dumps(config.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

from __future__ import annotations

from pathlib import Path

import yaml

SKIPPED_FILENAMES = {"pattern_examples.yaml"}
SECTION_FILE_ORDER = {
    "themes.yaml": 0,
    "section.yaml": 1,
    "bootstrap_words.yaml": 2,
    "patterns.yaml": 3,
}


def _yaml_sort_key(*, source_dir: Path, yaml_path: Path, ordered_sections: list[str]) -> tuple[int, int, int, str]:
    relative_path = yaml_path.relative_to(source_dir)
    if relative_path.parts == ("course.yaml",):
        return (0, -1, -1, "course.yaml")

    section_code = relative_path.parts[0]
    section_index = ordered_sections.index(section_code)
    file_rank = SECTION_FILE_ORDER.get(relative_path.name, len(SECTION_FILE_ORDER))
    return (1, section_index, file_rank, str(relative_path))


def main() -> int:
    backend_dir = Path(__file__).resolve().parent.parent
    source_dir = backend_dir / "config" / "en-ja-v1"
    output_path = backend_dir / "config" / "en-ja-v1_bundle.txt"
    course_payload = yaml.safe_load((source_dir / "course.yaml").read_text(encoding="utf-8"))
    ordered_sections = list(course_payload["sections"])

    yaml_paths = sorted(
        [
            yaml_path
            for yaml_path in source_dir.rglob("*.yaml")
            if yaml_path.name not in SKIPPED_FILENAMES
        ],
        key=lambda yaml_path: _yaml_sort_key(
            source_dir=source_dir,
            yaml_path=yaml_path,
            ordered_sections=ordered_sections,
        ),
    )
    if not yaml_paths:
        msg = f"No YAML files found under {source_dir}"
        raise ValueError(msg)

    sections: list[str] = []
    for yaml_path in yaml_paths:
        relative_path = yaml_path.relative_to(backend_dir)
        content = yaml_path.read_text(encoding="utf-8").rstrip()
        sections.append(f"{relative_path}\n{content}")

    output_path.write_text("\n\n".join(sections) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

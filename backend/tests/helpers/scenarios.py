from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UnitPlanScenario:
    key: str
    title: str
    description: str
    theme_codes: tuple[str, ...]

    def to_payload_entry(self) -> tuple[str, dict[str, object]]:
        return (
            self.key,
            {
                "title": self.title,
                "description": self.description,
                "theme_codes": list(self.theme_codes),
            },
        )


def build_unit_plan_payload(*scenarios: UnitPlanScenario) -> dict[str, object]:
    return dict(scenario.to_payload_entry() for scenario in scenarios)


def getting_started_unit_scenario() -> UnitPlanScenario:
    return UnitPlanScenario(
        key="unit_1",
        title="Getting Started",
        description="Identity and nearby objects.",
        theme_codes=("THEME_SELF_INTRO",),
    )


def water_review_unit_scenario() -> UnitPlanScenario:
    return UnitPlanScenario(
        key="unit_2",
        title="Water Review",
        description="Reuse course starter material.",
        theme_codes=("THEME_HOME_PLACE",),
    )


def single_intro_unit_plan_payload() -> dict[str, object]:
    return build_unit_plan_payload(getting_started_unit_scenario())


def intro_and_review_unit_plan_payload() -> dict[str, object]:
    return build_unit_plan_payload(
        getting_started_unit_scenario(),
        water_review_unit_scenario(),
    )


__all__ = [
    "UnitPlanScenario",
    "build_unit_plan_payload",
    "getting_started_unit_scenario",
    "intro_and_review_unit_plan_payload",
    "single_intro_unit_plan_payload",
    "water_review_unit_scenario",
]

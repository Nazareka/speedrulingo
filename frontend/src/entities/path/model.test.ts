import { describe, expect, it } from "vitest";
import type { PathResponse, SectionUnits, UnitSummary } from "../../shared/api/generated/types.gen";
import {
  allUnitsFlatFromPath,
  deriveInitialSelection,
  isCourseFullyCompleted,
  normalizePathSelection,
  pathSelectionForSectionChange,
  pathSelectionForUnitPick,
  pathSlidesForSection,
} from "./model";

function unit(
  id: string,
  sectionId: string,
  order: number,
  overrides: Partial<UnitSummary> = {},
): UnitSummary {
  return {
    id,
    section_id: sectionId,
    section_title: "",
    description: "",
    title: "U",
    unit_order_index: order,
    is_locked: false,
    is_completed: false,
    lesson_count: 0,
    completed_lessons: 0,
    lessons: [],
    ...overrides,
  };
}

function section(id: string, title: string, units: UnitSummary[]): SectionUnits {
  return { id, title, description: "", units };
}

describe("normalizePathSelection", () => {
  const data: PathResponse = {
    current_unit_id: null,
    current_lesson_id: null,
    sections: [
      section("s1", "A", [unit("u1", "s1", 2), unit("u2", "s1", 1)]),
      section("s2", "B", [unit("u3", "s2", 1)]),
    ],
  };

  it("maps null section + valid unit id to that unit’s section", () => {
    expect(normalizePathSelection(data, { selectedSectionId: null, selectedUnitId: "u3" })).toEqual(
      {
        selectedSectionId: "s2",
        selectedUnitId: "u3",
      },
    );
  });

  it("replaces unknown unit id with deriveInitialSelection(data, null), not a fake active id", () => {
    expect(
      normalizePathSelection(data, { selectedSectionId: null, selectedUnitId: "nope" }),
    ).toEqual(deriveInitialSelection(data, null));
  });

  it("uses deriveInitialSelection when both ids are null", () => {
    expect(normalizePathSelection(data, { selectedSectionId: null, selectedUnitId: null })).toEqual(
      deriveInitialSelection(data, null),
    );
  });
});

describe("sortedUnits reuse", () => {
  const data: PathResponse = {
    current_unit_id: null,
    current_lesson_id: null,
    sections: [section("s1", "Sec", [unit("u2", "s1", 2), unit("u1", "s1", 1)])],
  };

  it("pathSlidesForSection matches unit order from allUnitsFlatFromPath", () => {
    const slides = pathSlidesForSection(data, "s1");
    const flat = allUnitsFlatFromPath(data);
    expect(slides.map((s) => s.unit.id)).toEqual(["u1", "u2"]);
    expect(flat.filter((f) => f.unit.section_id === "s1").map((f) => f.unit.id)).toEqual([
      "u1",
      "u2",
    ]);
  });
});

describe("deriveInitialSelection", () => {
  it("selects the section and unit that contain activeUnitId", () => {
    const data: PathResponse = {
      current_unit_id: null,
      current_lesson_id: null,
      sections: [
        section("s1", "A", [unit("u1", "s1", 1)]),
        section("s2", "B", [unit("u2", "s2", 1)]),
      ],
    };
    expect(deriveInitialSelection(data, "u2")).toEqual({
      selectedSectionId: "s2",
      selectedUnitId: "u2",
    });
  });

  it("falls back to first unit of first section when activeUnitId is null or unknown", () => {
    const data: PathResponse = {
      current_unit_id: null,
      current_lesson_id: null,
      sections: [section("s1", "A", [unit("u1", "s1", 2), unit("u0", "s1", 1)])],
    };
    expect(deriveInitialSelection(data, null)).toEqual({
      selectedSectionId: "s1",
      selectedUnitId: "u0",
    });
    expect(deriveInitialSelection(data, "missing")).toEqual({
      selectedSectionId: "s1",
      selectedUnitId: "u0",
    });
  });
});

describe("pathSelectionForSectionChange", () => {
  const data: PathResponse = {
    current_unit_id: null,
    current_lesson_id: null,
    sections: [section("s1", "A", [unit("u2", "s1", 2), unit("u1", "s1", 1)])],
  };

  it("returns first unit in section order for a valid section", () => {
    expect(pathSelectionForSectionChange(data, "s1")).toEqual({
      selectedSectionId: "s1",
      selectedUnitId: "u1",
    });
  });

  it("returns null for an unknown section id", () => {
    expect(pathSelectionForSectionChange(data, "sx")).toBeNull();
  });
});

describe("pathSelectionForUnitPick", () => {
  const data: PathResponse = {
    current_unit_id: null,
    current_lesson_id: null,
    sections: [
      section("s1", "A", [unit("u1", "s1", 1)]),
      section("s2", "B", [unit("u2", "s2", 1)]),
    ],
  };

  it("returns normalized selection for a unit in the path", () => {
    expect(pathSelectionForUnitPick(data, "u2")).toEqual({
      selectedSectionId: "s2",
      selectedUnitId: "u2",
    });
  });

  it("returns null when unit id is not found", () => {
    expect(pathSelectionForUnitPick(data, "nope")).toBeNull();
  });
});

describe("isCourseFullyCompleted", () => {
  it("is false when there are no sections", () => {
    const data: PathResponse = {
      current_unit_id: null,
      current_lesson_id: null,
      sections: [],
    };
    expect(isCourseFullyCompleted(data)).toBe(false);
  });

  it("is false when any unit is incomplete", () => {
    const data: PathResponse = {
      current_unit_id: null,
      current_lesson_id: null,
      sections: [
        section("s1", "A", [unit("u1", "s1", 1, { is_completed: true }), unit("u2", "s1", 2)]),
      ],
    };
    expect(isCourseFullyCompleted(data)).toBe(false);
  });

  it("is true when every unit in every section is completed", () => {
    const data: PathResponse = {
      current_unit_id: null,
      current_lesson_id: null,
      sections: [
        section("s1", "A", [unit("u1", "s1", 1, { is_completed: true })]),
        section("s2", "B", [unit("u2", "s2", 1, { is_completed: true })]),
      ],
    };
    expect(isCourseFullyCompleted(data)).toBe(true);
  });

  it("is false when a section has zero units", () => {
    const data: PathResponse = {
      current_unit_id: null,
      current_lesson_id: null,
      sections: [
        section("s1", "A", []),
        section("s2", "B", [unit("u1", "s2", 1, { is_completed: true })]),
      ],
    };
    expect(isCourseFullyCompleted(data)).toBe(false);
  });
});

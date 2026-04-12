import { describe, expect, it } from "vitest";
import type { LessonSummary, UnitSummary } from "../../shared/api/generated/types.gen";
import { firstLessonIdForEntry, sortLessonsByOrderIndex } from "./unit-lessons";

function lesson(
  id: string,
  order_index: number,
  overrides: Partial<LessonSummary> = {},
): LessonSummary {
  return {
    id,
    order_index,
    kind: "normal",
    state: "not_started",
    is_locked: false,
    ...overrides,
  };
}

describe("firstLessonIdForEntry", () => {
  it("uses order_index, not array order, when picking head / first unlocked", () => {
    const unit: UnitSummary = {
      id: "u1",
      section_id: "s1",
      section_title: "S",
      description: "",
      title: "U",
      unit_order_index: 1,
      is_locked: false,
      is_completed: false,
      lesson_count: 2,
      completed_lessons: 0,
      lessons: [lesson("b", 2, { is_locked: false }), lesson("a", 1, { is_locked: false })],
    };
    expect(firstLessonIdForEntry(unit)).toBe("a");
  });

  it("sortLessonsByOrderIndex orders by order_index", () => {
    const lessons = [lesson("z", 3), lesson("a", 1), lesson("m", 2)];
    const ordered = sortLessonsByOrderIndex(lessons);
    expect(ordered.map((l) => l.id)).toEqual(["a", "m", "z"]);
  });

  it("prefers first unlocked lesson when the ordered head is locked", () => {
    const u: UnitSummary = {
      id: "u1",
      section_id: "s1",
      section_title: "S",
      description: "",
      title: "U",
      unit_order_index: 1,
      is_locked: false,
      is_completed: false,
      lesson_count: 2,
      completed_lessons: 0,
      lessons: [lesson("a", 1, { is_locked: true }), lesson("b", 2, { is_locked: false })],
    };
    expect(firstLessonIdForEntry(u)).toBe("b");
  });
});

import { describe, expect, it } from "vitest";

import {
  focusLessonIdForCircleChain,
  lessonChainRowVm,
} from "../../pages/path/lesson-circle-chain-vm";
import type { LessonSummary } from "../../shared/api/generated/types.gen";

function lesson(id: string, order: number, overrides: Partial<LessonSummary> = {}): LessonSummary {
  return {
    id,
    order_index: order,
    kind: "normal",
    state: "not_started",
    is_locked: false,
    ...overrides,
  };
}

describe("lessonChainRowVm", () => {
  it("has no connector on the first row", () => {
    const l = lesson("a", 1);
    const row = lessonChainRowVm(l, null, "a", false);
    expect(row.connectorBefore).toBeNull();
  });

  it("uses gradient connector when both lessons completed", () => {
    const prev = lesson("p", 0, { state: "completed" });
    const cur = lesson("c", 1, { state: "completed" });
    const row = lessonChainRowVm(cur, prev, null, false);
    expect(row.connectorBefore?.isGradient).toBe(true);
    expect(row.connectorBefore?.style?.backgroundImage).toContain("linear-gradient");
  });

  it("marks interactive when unit and lesson are unlocked", () => {
    const l = lesson("a", 0, { state: "not_started", is_locked: false });
    const row = lessonChainRowVm(l, null, "a", false);
    expect(row.isInteractive).toBe(true);
  });

  it("is not interactive when unit is locked", () => {
    const l = lesson("a", 0, { state: "not_started", is_locked: false });
    const row = lessonChainRowVm(l, null, "a", true);
    expect(row.isInteractive).toBe(false);
    expect(row.showLockIcon).toBe(true);
  });
});

describe("focusLessonIdForCircleChain", () => {
  it("returns null when unit is locked or ordered is empty", () => {
    expect(focusLessonIdForCircleChain([], null, true, false)).toBeNull();
    expect(focusLessonIdForCircleChain([lesson("a", 1)], null, true, true)).toBeNull();
  });

  it("uses currentLessonId when API active unit matches a lesson in the chain", () => {
    const ordered = [lesson("a", 1), lesson("b", 2)];
    expect(focusLessonIdForCircleChain(ordered, "b", true, false)).toBe("b");
  });

  it("uses first incomplete lesson when current lesson is not in chain", () => {
    const ordered = [
      lesson("a", 1, { state: "completed" }),
      lesson("b", 2, { state: "not_started" }),
    ];
    expect(focusLessonIdForCircleChain(ordered, "other", true, false)).toBe("b");
  });
});

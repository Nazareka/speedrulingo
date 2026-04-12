import { describe, expect, it } from "vitest";

import { buildOrderedCompletionAnswers } from "../../../shared/lesson/session-completion";
import {
  lessonCurrentIndex,
  lessonTotalCount,
  progressBarCssWidth,
  remainingReviewCount,
  topBarCompletedItemCount,
} from "../../../shared/lesson/session-model";

describe("progressBarCssWidth", () => {
  it("returns percentage width clamped to 0–100", () => {
    expect(progressBarCssWidth(0, 10)).toBe("0%");
    expect(progressBarCssWidth(5, 10)).toBe("50%");
    expect(progressBarCssWidth(10, 10)).toBe("100%");
  });

  it("uses at least 1 as total to avoid division by zero", () => {
    expect(progressBarCssWidth(3, 0)).toBe("100%");
    expect(progressBarCssWidth(1, 1)).toBe("100%");
  });
});

describe("topBarCompletedItemCount", () => {
  it("uses progressCompletedCount when provided", () => {
    expect(
      topBarCompletedItemCount({
        currentIndex: 3,
        totalCount: 10,
        progressCompletedCount: 10,
      }),
    ).toBe(10);
  });

  it("falls back to currentIndex - 1", () => {
    expect(topBarCompletedItemCount({ currentIndex: 4, totalCount: 10 })).toBe(3);
  });
});

describe("lessonTotalCount", () => {
  it("prefers totalItems then current item total", () => {
    expect(lessonTotalCount(5, 99)).toBe(5);
    expect(lessonTotalCount(null, 7)).toBe(7);
    expect(lessonTotalCount(null, undefined)).toBe(1);
  });
});

describe("lessonCurrentIndex", () => {
  it("caps at totalCount", () => {
    expect(lessonCurrentIndex(9, 10)).toBe(10);
    expect(lessonCurrentIndex(10, 10)).toBe(10);
  });
});

describe("remainingReviewCount", () => {
  it("adds one when current entry is review", () => {
    expect(remainingReviewCount(2, "review")).toBe(3);
    expect(remainingReviewCount(2, "main")).toBe(2);
    expect(remainingReviewCount(2, null)).toBe(2);
  });
});

describe("buildOrderedCompletionAnswers", () => {
  it("returns ordered answers when all items have final answers", () => {
    const itemCache = {
      a: { order_index: 1, item_id: "a" },
      b: { order_index: 0, item_id: "b" },
    } as unknown as Record<
      string,
      import("../../../shared/api/generated/types.gen").LessonItemResponse
    >;
    const finalAnswers = { a: "x", b: "y" };
    const result = buildOrderedCompletionAnswers(itemCache, finalAnswers);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.answers.map((x) => x.itemId)).toEqual(["b", "a"]);
    }
  });

  it("fails when an item is missing a final answer", () => {
    const itemCache = {
      a: { order_index: 0, item_id: "a" },
      b: { order_index: 1, item_id: "b" },
    } as unknown as Record<
      string,
      import("../../../shared/api/generated/types.gen").LessonItemResponse
    >;
    const finalAnswers = { a: "only" };
    const result = buildOrderedCompletionAnswers(itemCache, finalAnswers);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.reason).toBe("missing_answers");
    }
  });
});

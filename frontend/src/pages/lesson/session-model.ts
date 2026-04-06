import type { LessonItemResponse } from "../../shared/api/generated/types.gen";

/** CSS width string for the lesson progress bar (e.g. `"45%"`). */
export function progressBarCssWidth(completedCount: number, totalCount: number): string {
  const safeTotal = Math.max(totalCount, 1);
  const percent = (completedCount / safeTotal) * 100;
  return `${Math.max(0, Math.min(percent, 100))}%`;
}

/** Completed “steps” count used to fill the top bar (clamped to `totalCount`). */
export function topBarCompletedItemCount(params: {
  currentIndex: number;
  totalCount: number;
  progressCompletedCount?: number;
}): number {
  const { currentIndex, totalCount, progressCompletedCount } = params;
  if (progressCompletedCount !== undefined) {
    return Math.min(progressCompletedCount, totalCount);
  }
  return Math.max(currentIndex - 1, 0);
}

export function lessonTotalCount(
  totalItems: number | null,
  currentItemTotalItems: number | undefined,
): number {
  return totalItems ?? currentItemTotalItems ?? 1;
}

export function lessonCurrentIndex(completedItemIdsLength: number, totalCount: number): number {
  return Math.min(completedItemIdsLength + 1, totalCount);
}

export function remainingReviewCount(
  reviewQueueLength: number,
  currentEntrySource: "main" | "review" | null,
): number {
  return reviewQueueLength + (currentEntrySource === "review" ? 1 : 0);
}

export function hasMoreMainItemsToLoad(
  totalItems: number | null,
  nextCursorToLoad: number,
): boolean {
  return totalItems !== null && nextCursorToLoad < totalItems;
}

type CompletionPayloadResult =
  | { ok: true; answers: Array<{ itemId: string; userAnswer: string }> }
  | { ok: false; reason: "missing_answers" };

/**
 * Builds ordered submit payload from cached items and stored correct answers.
 * Returns `missing_answers` if any cached item lacks a final answer.
 */
export function buildOrderedCompletionAnswers(
  itemCache: Record<string, LessonItemResponse>,
  finalAnswers: Record<string, string>,
): CompletionPayloadResult {
  const orderedAnswers = Object.entries(itemCache)
    .sort(([, left], [, right]) => left.order_index - right.order_index)
    .map(([itemId]) => ({
      itemId,
      userAnswer: finalAnswers[itemId],
    }))
    .filter(
      (entry): entry is { itemId: string; userAnswer: string } => entry.userAnswer !== undefined,
    );

  if (orderedAnswers.length !== Object.keys(itemCache).length) {
    return { ok: false, reason: "missing_answers" };
  }
  return { ok: true, answers: orderedAnswers };
}

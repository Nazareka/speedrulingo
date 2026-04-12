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

import type { LessonSummary, UnitSummary } from "../../shared/api/generated/types.gen";

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n));
}

/** Lessons in API order_index order (stable copy). */
export function sortLessonsByOrderIndex(lessons: LessonSummary[]): LessonSummary[] {
  return [...lessons].sort((a, b) => a.order_index - b.order_index);
}

/**
 * First lesson the learner can open (prefer unlocked).
 * Lessons are sorted by `order_index` before choosing head / first unlocked.
 */
export function firstLessonIdForEntry(unit: UnitSummary): string | null {
  const ordered = sortLessonsByOrderIndex(unit.lessons);
  const head = ordered[0];
  if (head === undefined) return null;
  const firstOpen = ordered.find((l) => !l.is_locked);
  return (firstOpen ?? head).id;
}

/**
 * CSS width string for a horizontal progress bar (0–100%).
 * Presentation output only; pair with domain counts from API models.
 */
export function progressWidthPercent(completed: number, total: number): string {
  const safeTotal = Math.max(total, 1);
  const percent = (completed / safeTotal) * 100;
  return `${clamp(percent, 0, 100)}%`;
}

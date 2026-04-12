import type { LessonItemResponse } from "../api/generated/types.gen";

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

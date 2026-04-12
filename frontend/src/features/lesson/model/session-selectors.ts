import type { DraftAnswer, FeedbackState } from "../../../entities/lesson/session-types";
import type { LessonItemResponse } from "../../../shared/api/generated/types.gen";
import { isMultipleChoiceItem, normalizeAnswer } from "./item-helpers";
import { stableShuffle } from "./tile-helpers";

/** Normalized answer string for the active item from draft + item kind. */
export function draftUserAnswer(
  currentItem: LessonItemResponse | undefined,
  draft: DraftAnswer,
): string {
  if (!currentItem) {
    return "";
  }
  if (isMultipleChoiceItem(currentItem)) {
    return draft.kind === "choice" ? (draft.selectedOption ?? "") : "";
  }
  return draft.kind === "tiles" ? normalizeAnswer(draft.selectedTiles) : "";
}

/** Whether the user could submit a check, ignoring async mutation pending state. */
export function lessonCanCheckDraft(
  currentAnswer: string,
  feedback: FeedbackState | null,
  isLessonFinished: boolean,
): boolean {
  return currentAnswer.length > 0 && feedback === null && !isLessonFinished;
}

/**
 * Word-bank tiles still available (same shuffle key as the exercise panel).
 */
export function computeAvailableSentenceTiles(
  currentItem: LessonItemResponse | undefined,
  selectedTiles: Array<string>,
): Array<string> {
  if (!currentItem || currentItem.item_type !== "sentence_tiles") {
    return [];
  }
  const remaining = stableShuffle(
    [...currentItem.answer_tiles],
    `${currentItem.item_id}:${currentItem.prompt_text}:sentence-tiles`,
  );
  for (const tile of selectedTiles) {
    const index = remaining.indexOf(tile);
    if (index >= 0) {
      remaining.splice(index, 1);
    }
  }
  return remaining;
}

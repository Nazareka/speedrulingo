import type { LessonItemResponse } from "../../shared/api/generated/types.gen";

import type { DraftAnswer } from "./session-types";

/** `LessonItemResponse` is a flat type; this narrows `item_type` to multiple-choice kinds. */
export type MultipleChoiceLessonItem = Omit<LessonItemResponse, "item_type"> & {
  item_type: "word_choice" | "kanji_kana_match";
};

export function isMultipleChoiceItem(
  item: LessonItemResponse | null | undefined,
): item is MultipleChoiceLessonItem {
  return (
    item != null && (item.item_type === "word_choice" || item.item_type === "kanji_kana_match")
  );
}

export function emptyDraftForItem(item: LessonItemResponse | null | undefined): DraftAnswer {
  if (item && isMultipleChoiceItem(item)) {
    return { kind: "choice", selectedOption: null };
  }
  return { kind: "tiles", selectedTiles: [] };
}

export function normalizeAnswer(parts: Array<string>): string {
  return parts.join(" ").trim();
}

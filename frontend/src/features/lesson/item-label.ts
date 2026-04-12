import type { LessonItemResponse } from "../../shared/api/generated/types.gen";

export function lessonItemLabel(itemType: LessonItemResponse["item_type"]) {
  if (itemType === "word_choice") {
    return "Word match";
  }
  if (itemType === "kanji_kana_match") {
    return "Match kanji and kana";
  }
  return "Build a sentence";
}

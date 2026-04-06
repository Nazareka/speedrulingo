import type { LessonItemResponse } from "../../shared/api/generated/types.gen";

import { emptyDraftForItem } from "./item-helpers";
import type { FeedbackState, LessonSessionState } from "./session-types";

const ADVANCE_MISSING_ANSWERS_MESSAGE =
  "Could not finish the lesson: some answers are missing. Try again or contact support.";

export function clearAdvanceInvariantError(prev: LessonSessionState): LessonSessionState {
  return { ...prev, advanceInvariantError: null };
}

export function applyAfterMainItemLoaded(
  prev: LessonSessionState,
  nextItem: LessonItemResponse,
): LessonSessionState {
  return {
    ...prev,
    draft: emptyDraftForItem(nextItem),
    feedback: null,
    itemCache: { ...prev.itemCache, [nextItem.item_id]: nextItem },
    nextCursorToLoad: prev.nextCursorToLoad + 1,
    currentQueueEntry: { itemId: nextItem.item_id, source: "main" },
  };
}

/** Call only when `reviewQueue.length > 0`. */
export function applyNextReviewStep(prev: LessonSessionState): LessonSessionState {
  const nextReview = prev.reviewQueue[0];
  if (nextReview === undefined) {
    return prev;
  }
  const remainingReview = prev.reviewQueue.slice(1);
  return {
    ...prev,
    draft: emptyDraftForItem(prev.itemCache[nextReview.itemId]),
    feedback: null,
    reviewQueue: remainingReview,
    currentQueueEntry: nextReview,
  };
}

export function applyAdvanceInvariantMissingAnswers(prev: LessonSessionState): LessonSessionState {
  return { ...prev, advanceInvariantError: ADVANCE_MISSING_ANSWERS_MESSAGE };
}

export function applyAfterLessonComplete(
  prev: LessonSessionState,
  progressState: string,
): LessonSessionState {
  return {
    ...prev,
    draft: emptyDraftForItem(undefined),
    feedback: null,
    completionProgressState: progressState,
    isLessonFinished: true,
    currentQueueEntry: null,
  };
}

export function feedbackFromCheckItemResult(itemResult: {
  expected_answer: string;
  is_correct: boolean;
  user_answer: string;
}): FeedbackState {
  return {
    expectedAnswer: itemResult.expected_answer,
    isCorrect: itemResult.is_correct,
    submittedAnswer: itemResult.user_answer,
  };
}

export function applyCorrectCheck(
  prev: LessonSessionState,
  itemId: string,
  feedback: FeedbackState,
  expectedAnswer: string,
): LessonSessionState {
  return {
    ...prev,
    feedback,
    correctCount: prev.correctCount + 1,
    finalAnswers: { ...prev.finalAnswers, [itemId]: expectedAnswer },
    completedItemIds: prev.completedItemIds.includes(itemId)
      ? prev.completedItemIds
      : [...prev.completedItemIds, itemId],
  };
}

export function applyIncorrectCheck(
  prev: LessonSessionState,
  itemId: string,
  feedback: FeedbackState,
): LessonSessionState {
  return {
    ...prev,
    feedback,
    mistakeCount: prev.mistakeCount + 1,
    reviewQueue: [...prev.reviewQueue, { itemId, source: "review" }],
  };
}

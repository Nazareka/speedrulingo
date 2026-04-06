import type { LessonSessionState } from "./session-types";

export function createInitialLessonSessionState(): LessonSessionState {
  return {
    itemCache: {},
    currentQueueEntry: null,
    reviewQueue: [],
    nextCursorToLoad: 0,
    totalItems: null,
    completedItemIds: [],
    finalAnswers: {},
    draft: { kind: "tiles", selectedTiles: [] },
    feedback: null,
    correctCount: 0,
    mistakeCount: 0,
    isLessonFinished: false,
    completionProgressState: null,
    isInitializing: true,
    initError: null,
    loadAttempt: 0,
    advanceInvariantError: null,
    isLeaveDialogOpen: false,
  };
}

/** Reset queue/progress/draft for a new load attempt; preserves `loadAttempt` for retry UX. */
export function resetSessionForLessonInit(prev: LessonSessionState): LessonSessionState {
  return {
    ...createInitialLessonSessionState(),
    loadAttempt: prev.loadAttempt,
  };
}

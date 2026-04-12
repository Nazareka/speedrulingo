import type { LessonItemResponse } from "../api/generated/types.gen";

export type FeedbackState = {
  expectedAnswer: string;
  isCorrect: boolean;
  submittedAnswer: string;
};

export type QueueEntry = {
  itemId: string;
  source: "main" | "review";
};

/** Draft answer for the active item; discriminated by exercise type. */
export type DraftAnswer =
  | { kind: "choice"; selectedOption: string | null }
  | { kind: "tiles"; selectedTiles: Array<string> };

/** Single object for lesson runtime fields (queue, draft, feedback, completion). */
export type LessonSessionState = {
  itemCache: Record<string, LessonItemResponse>;
  currentQueueEntry: QueueEntry | null;
  reviewQueue: QueueEntry[];
  nextCursorToLoad: number;
  totalItems: number | null;
  completedItemIds: Array<string>;
  finalAnswers: Record<string, string>;
  draft: DraftAnswer;
  feedback: FeedbackState | null;
  correctCount: number;
  mistakeCount: number;
  isLessonFinished: boolean;
  completionProgressState: string | null;
  isInitializing: boolean;
  initError: string | null;
  loadAttempt: number;
  advanceInvariantError: string | null;
  isLeaveDialogOpen: boolean;
};

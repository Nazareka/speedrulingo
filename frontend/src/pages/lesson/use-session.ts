import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  useCheckLessonAnswer,
  useCompleteLesson,
  useLoadLessonItem,
} from "../../features/lesson-runner/queries";
import { pathKeys } from "../../features/path/queries";
import { unitKeys } from "../../features/units/queries";
import type { LessonItemResponse } from "../../shared/api/generated/types.gen";
import { getErrorMessage } from "../../shared/lib/api-error";
import {
  buildOrderedCompletionAnswers,
  hasMoreMainItemsToLoad,
  lessonCurrentIndex,
  lessonTotalCount,
  remainingReviewCount as remainingReviewCountModel,
  topBarCompletedItemCount,
} from "./session-model";
import {
  computeAvailableSentenceTiles,
  draftUserAnswer,
  lessonCanCheckDraft,
} from "./session-selectors";
import { createInitialLessonSessionState, resetSessionForLessonInit } from "./session-state";
import {
  applyAdvanceInvariantMissingAnswers,
  applyAfterLessonComplete,
  applyAfterMainItemLoaded,
  applyCorrectCheck,
  applyIncorrectCheck,
  applyNextReviewStep,
  clearAdvanceInvariantError,
  feedbackFromCheckItemResult,
} from "./session-transitions";
import type { FeedbackState } from "./session-types";
import { isLessonAnswerControlTarget, isSpaceTargetInsideInteractiveControl } from "./shortcuts";
import { buildTileInstances } from "./tile-helpers";

type UseLessonSessionResult = {
  currentItem: LessonItemResponse | undefined;
  selectedTiles: Array<string>;
  selectedOption: string | null;
  selectOption: (option: string) => void;
  addTile: (tile: string) => void;
  removeTileAt: (index: number) => void;
  feedback: FeedbackState | null;
  correctCount: number;
  mistakeCount: number;
  isLessonFinished: boolean;
  completionProgressState: string | null;
  isInitializing: boolean;
  initError: string | null;
  advanceInvariantError: string | null;
  isLeaveDialogOpen: boolean;
  openLeaveDialog: () => void;
  closeLeaveDialog: () => void;
  retryInitLoad: () => void;
  selectedTileInstances: ReturnType<typeof buildTileInstances>;
  availableTileInstances: ReturnType<typeof buildTileInstances>;
  canCheck: boolean;
  totalCount: number;
  currentIndex: number;
  /** Completed steps used only for the progress bar fill (not the same as step label when finished). */
  progressBarFillCompletedCount: number;
  remainingReviewCount: number;
  checkAnswerError: string | null;
  continueFooterError: string | null;
  continuePending: boolean;
  isCheckAnswerPending: boolean;
  advanceQueue: () => Promise<void>;
  handleCheck: () => Promise<void>;
};

export function useLessonSession(lessonId: string): UseLessonSessionResult {
  const queryClient = useQueryClient();
  const nextItemMutation = useLoadLessonItem(lessonId);
  const checkAnswerMutation = useCheckLessonAnswer(lessonId);
  const completeLessonMutation = useCompleteLesson(lessonId);
  const advanceQueueRef = useRef<() => Promise<void>>(async () => {});
  const handleCheckRef = useRef<() => Promise<void>>(async () => {});
  const isAdvancingRef = useRef(false);
  const isCheckingRef = useRef(false);

  const [session, setSession] = useState(createInitialLessonSessionState);
  const {
    itemCache,
    currentQueueEntry,
    reviewQueue,
    nextCursorToLoad,
    totalItems,
    completedItemIds,
    finalAnswers,
    draft,
    feedback,
    correctCount,
    mistakeCount,
    isLessonFinished,
    completionProgressState,
    isInitializing,
    initError,
    loadAttempt,
    advanceInvariantError,
    isLeaveDialogOpen,
  } = session;

  const selectedTiles = draft.kind === "tiles" ? draft.selectedTiles : [];
  const selectedOption = draft.kind === "choice" ? draft.selectedOption : null;

  const selectOption = useCallback((option: string) => {
    setSession((s) => {
      if (s.draft.kind !== "choice") {
        return s;
      }
      return {
        ...s,
        draft: { kind: "choice", selectedOption: option },
      };
    });
  }, []);

  const addTile = useCallback((tile: string) => {
    setSession((s) => {
      if (s.draft.kind !== "tiles") {
        return s;
      }
      return {
        ...s,
        draft: { kind: "tiles", selectedTiles: [...s.draft.selectedTiles, tile] },
      };
    });
  }, []);

  const removeTileAt = useCallback((index: number) => {
    setSession((s) => {
      if (s.draft.kind !== "tiles") {
        return s;
      }
      return {
        ...s,
        draft: {
          kind: "tiles",
          selectedTiles: s.draft.selectedTiles.filter((_, i) => i !== index),
        },
      };
    });
  }, []);

  const openLeaveDialog = useCallback(() => {
    setSession((s) => ({ ...s, isLeaveDialogOpen: true }));
  }, []);

  const closeLeaveDialog = useCallback(() => {
    setSession((s) => ({ ...s, isLeaveDialogOpen: false }));
  }, []);

  const retryInitLoad = useCallback(() => {
    setSession((s) => ({ ...s, loadAttempt: s.loadAttempt + 1 }));
  }, []);

  // Refs mirror the latest route/session identity so async handlers can reject stale results after await.
  const loadAttemptRef = useRef(loadAttempt);
  loadAttemptRef.current = loadAttempt;

  const lessonIdRef = useRef(lessonId);
  lessonIdRef.current = lessonId;

  const currentItem = currentQueueEntry ? itemCache[currentQueueEntry.itemId] : undefined;

  useEffect(() => {
    let isCancelled = false;
    const attemptWhenStarted = loadAttempt;

    async function initializeLesson() {
      const requestedLessonId = lessonId;
      setSession((prev) => ({
        ...resetSessionForLessonInit(prev),
        isInitializing: true,
        initError: null,
      }));

      try {
        const firstItem = await nextItemMutation.mutateAsync(0);
        if (isCancelled || lessonIdRef.current !== requestedLessonId) {
          return;
        }
        if (loadAttemptRef.current !== attemptWhenStarted) {
          return;
        }
        setSession((prev) => ({
          ...applyAfterMainItemLoaded(prev, firstItem),
          totalItems: firstItem.total_items,
        }));
      } catch (error) {
        if (
          !isCancelled &&
          lessonIdRef.current === requestedLessonId &&
          loadAttemptRef.current === attemptWhenStarted
        ) {
          setSession((prev) => ({
            ...prev,
            initError: getErrorMessage(error),
          }));
        }
      } finally {
        if (!isCancelled && loadAttemptRef.current === attemptWhenStarted) {
          setSession((prev) => ({ ...prev, isInitializing: false }));
        }
      }
    }

    void initializeLesson();

    return () => {
      isCancelled = true;
    };
  }, [lessonId, loadAttempt, nextItemMutation.mutateAsync]);

  const availableTiles = useMemo(
    () => computeAvailableSentenceTiles(currentItem, selectedTiles),
    [currentItem, selectedTiles],
  );

  const selectedTileInstances = useMemo(() => buildTileInstances(selectedTiles), [selectedTiles]);
  const availableTileInstances = useMemo(
    () => buildTileInstances(availableTiles),
    [availableTiles],
  );

  const currentAnswer = draftUserAnswer(currentItem, draft);

  const canCheck =
    lessonCanCheckDraft(currentAnswer, feedback, isLessonFinished) &&
    !checkAnswerMutation.isPending;

  async function advanceQueue() {
    if (isAdvancingRef.current) {
      return;
    }
    isAdvancingRef.current = true;

    const lessonWhenStarted = lessonId;

    try {
      setSession(clearAdvanceInvariantError);

      if (hasMoreMainItemsToLoad(totalItems, nextCursorToLoad)) {
        const nextItem = await nextItemMutation.mutateAsync(nextCursorToLoad);
        if (lessonIdRef.current !== lessonWhenStarted) {
          return;
        }
        setSession((prev) => applyAfterMainItemLoaded(prev, nextItem));
        return;
      }

      if (reviewQueue.length > 0) {
        if (lessonIdRef.current !== lessonWhenStarted) {
          return;
        }
        setSession(applyNextReviewStep);
        return;
      }

      const completion = buildOrderedCompletionAnswers(itemCache, finalAnswers);
      if (!completion.ok) {
        if (lessonIdRef.current !== lessonWhenStarted) {
          return;
        }
        setSession(applyAdvanceInvariantMissingAnswers);
        return;
      }

      const result = await completeLessonMutation.mutateAsync({
        answers: completion.answers,
      });
      if (lessonIdRef.current !== lessonWhenStarted) {
        return;
      }
      setSession((prev) => applyAfterLessonComplete(prev, result.progress_state));
      void queryClient.invalidateQueries({ queryKey: pathKeys.all });
      void queryClient.invalidateQueries({ queryKey: unitKeys.all });
    } catch {
      // Failed loads keep feedback + draft; errors surface via mutation.error or advanceInvariantError.
    } finally {
      isAdvancingRef.current = false;
    }
  }

  async function handleCheck() {
    if (!currentItem || isCheckingRef.current) {
      return;
    }
    isCheckingRef.current = true;

    const itemIdWhenStarted = currentItem.item_id;
    const lessonWhenStarted = lessonId;

    try {
      const result = await checkAnswerMutation.mutateAsync({
        itemId: itemIdWhenStarted,
        userAnswer: currentAnswer,
      });
      if (lessonIdRef.current !== lessonWhenStarted) {
        return;
      }
      const itemResult = result.item_results[0];
      if (!itemResult) {
        return;
      }

      const feedbackPatch: FeedbackState = feedbackFromCheckItemResult(itemResult);

      if (itemResult.is_correct) {
        setSession((prev) => {
          if (prev.currentQueueEntry?.itemId !== itemIdWhenStarted) {
            return prev;
          }
          return applyCorrectCheck(
            prev,
            itemIdWhenStarted,
            feedbackPatch,
            itemResult.expected_answer,
          );
        });
        return;
      }

      setSession((prev) => {
        if (prev.currentQueueEntry?.itemId !== itemIdWhenStarted) {
          return prev;
        }
        return applyIncorrectCheck(prev, itemIdWhenStarted, feedbackPatch);
      });
    } catch {
      // checkAnswerMutation.error is shown in the check zone.
    } finally {
      isCheckingRef.current = false;
    }
  }

  const totalCount = lessonTotalCount(totalItems, currentItem?.total_items);
  const currentIndex = lessonCurrentIndex(completedItemIds.length, totalCount);
  const progressBarFillCompletedCount = useMemo(() => {
    if (isLessonFinished) {
      return totalCount;
    }
    return topBarCompletedItemCount({ currentIndex, totalCount });
  }, [isLessonFinished, currentIndex, totalCount]);
  const remainingReviewCount = remainingReviewCountModel(
    reviewQueue.length,
    currentQueueEntry?.source ?? null,
  );
  const checkAnswerError = checkAnswerMutation.error
    ? getErrorMessage(checkAnswerMutation.error)
    : null;
  const completeLessonError = completeLessonMutation.error
    ? getErrorMessage(completeLessonMutation.error)
    : null;
  const nextItemLoadError = nextItemMutation.error ? getErrorMessage(nextItemMutation.error) : null;
  const continueFooterError = advanceInvariantError ?? nextItemLoadError ?? completeLessonError;
  const continuePending = nextItemMutation.isPending || completeLessonMutation.isPending;

  advanceQueueRef.current = advanceQueue;
  handleCheckRef.current = handleCheck;

  useEffect(() => {
    function handleWindowKeyDown(event: KeyboardEvent) {
      if (event.code !== "Space") {
        return;
      }

      if (isSpaceTargetInsideInteractiveControl(event.target)) {
        // Focus usually stays on the selected choice / tile button; native Space would click, not Check.
        if (!(canCheck && !feedback && isLessonAnswerControlTarget(event.target))) {
          return;
        }
      }

      if (
        isLeaveDialogOpen ||
        isLessonFinished ||
        checkAnswerMutation.isPending ||
        completeLessonMutation.isPending ||
        nextItemMutation.isPending
      ) {
        return;
      }

      if (feedback) {
        event.preventDefault();
        void advanceQueueRef.current();
        return;
      }

      if (canCheck) {
        event.preventDefault();
        const active = document.activeElement;
        if (active instanceof HTMLElement && isLessonAnswerControlTarget(active)) {
          active.blur();
        }
        void handleCheckRef.current();
      }
    }

    window.addEventListener("keydown", handleWindowKeyDown);
    return () => {
      window.removeEventListener("keydown", handleWindowKeyDown);
    };
  }, [
    canCheck,
    feedback,
    isLeaveDialogOpen,
    isLessonFinished,
    checkAnswerMutation.isPending,
    completeLessonMutation.isPending,
    nextItemMutation.isPending,
  ]);

  return {
    currentItem,
    selectedTiles,
    selectedOption,
    selectOption,
    addTile,
    removeTileAt,
    feedback,
    correctCount,
    mistakeCount,
    isLessonFinished,
    completionProgressState,
    isInitializing,
    initError,
    advanceInvariantError,
    isLeaveDialogOpen,
    openLeaveDialog,
    closeLeaveDialog,
    retryInitLoad,
    selectedTileInstances,
    availableTileInstances,
    canCheck,
    totalCount,
    currentIndex,
    progressBarFillCompletedCount,
    remainingReviewCount,
    checkAnswerError,
    continueFooterError,
    continuePending,
    isCheckAnswerPending: checkAnswerMutation.isPending,
    advanceQueue,
    handleCheck,
  };
}

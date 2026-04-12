import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { KanaLessonItemResponse } from "../../shared/api/generated/types.gen";
import {
  hasMoreMainItemsToLoad,
  lessonCurrentIndex,
  lessonTotalCount,
  remainingReviewCount as remainingReviewCountModel,
  topBarCompletedItemCount,
} from "../../shared/lesson/session-model";
import type { FeedbackState, QueueEntry } from "../../shared/lesson/session-types";
import { useLessonSpaceShortcut } from "../../shared/lesson/use-lesson-space-shortcut";
import { getErrorMessage } from "../../shared/lib/api-error";
import { loadKanaLessonItem, refreshKanaOverviewQuery, useSubmitKanaLesson } from "./queries";

function isAbortLikeError(error: unknown): boolean {
  if (error instanceof DOMException && error.name === "AbortError") {
    return true;
  }
  return error instanceof Error && error.name === "AbortError";
}

type KanaLessonState = {
  itemCache: Record<string, KanaLessonItemResponse>;
  currentQueueEntry: QueueEntry | null;
  reviewQueue: QueueEntry[];
  nextCursorToLoad: number;
  totalItems: number | null;
  completedItemIds: string[];
  finalAnswers: Record<string, string>;
  feedback: FeedbackState | null;
  correctCount: number;
  mistakeCount: number;
  isLessonFinished: boolean;
  completionProgressState: string | null;
  isInitializing: boolean;
  initError: string | null;
  loadAttempt: number;
  continueError: string | null;
  isLeaveDialogOpen: boolean;
};

function initialState(): KanaLessonState {
  return {
    itemCache: {},
    currentQueueEntry: null,
    reviewQueue: [],
    nextCursorToLoad: 0,
    totalItems: null,
    completedItemIds: [],
    finalAnswers: {},
    feedback: null,
    correctCount: 0,
    mistakeCount: 0,
    isLessonFinished: false,
    completionProgressState: null,
    isInitializing: true,
    initError: null,
    loadAttempt: 0,
    continueError: null,
    isLeaveDialogOpen: false,
  };
}

function optionChar(item: KanaLessonItemResponse, optionId: string): string {
  return item.answer_options.find((option) => option.option_id === optionId)?.char ?? optionId;
}

function orderedCompletionAnswers(
  itemCache: Record<string, KanaLessonItemResponse>,
  finalAnswers: Record<string, string>,
): Array<{ itemId: string; optionId: string }> | null {
  const ordered = Object.entries(itemCache)
    .sort(([, left], [, right]) => left.order_index - right.order_index)
    .map(([itemId]) => ({ itemId, optionId: finalAnswers[itemId] }));
  if (ordered.some((entry) => entry.optionId === undefined)) {
    return null;
  }
  return ordered as Array<{ itemId: string; optionId: string }>;
}

export function useKanaLessonSession(lessonId: string) {
  const queryClient = useQueryClient();
  const submitMutation = useSubmitKanaLesson(lessonId);
  const [session, setSession] = useState(initialState);
  const [selectedOptionId, setSelectedOptionId] = useState<string | null>(null);
  const [isNextMainItemPending, setIsNextMainItemPending] = useState(false);
  const nextMainItemLoadAbortRef = useRef<AbortController | null>(null);
  const lessonIdRef = useRef(lessonId);
  lessonIdRef.current = lessonId;
  const loadAttemptRef = useRef(session.loadAttempt);
  loadAttemptRef.current = session.loadAttempt;

  // biome-ignore lint/correctness/useExhaustiveDependencies: abort in-flight next-item fetch when route `lessonId` changes
  useEffect(() => {
    return () => {
      nextMainItemLoadAbortRef.current?.abort();
    };
  }, [lessonId]);

  const currentItem = session.currentQueueEntry
    ? session.itemCache[session.currentQueueEntry.itemId]
    : undefined;

  useEffect(() => {
    let cancelled = false;
    const abortController = new AbortController();
    const attemptWhenStarted = session.loadAttempt;
    setSelectedOptionId(null);
    setSession((prev) => ({
      ...initialState(),
      loadAttempt: prev.loadAttempt,
      isInitializing: true,
    }));

    async function initialize() {
      try {
        const firstItem = await loadKanaLessonItem(lessonId, 0, abortController.signal);
        if (
          cancelled ||
          lessonIdRef.current !== lessonId ||
          loadAttemptRef.current !== attemptWhenStarted
        ) {
          return;
        }
        setSession((prev) => ({
          ...prev,
          itemCache: { [firstItem.item_id]: firstItem },
          currentQueueEntry: { itemId: firstItem.item_id, source: "main" },
          nextCursorToLoad: 1,
          totalItems: firstItem.total_items,
          isInitializing: false,
        }));
      } catch (error) {
        if (isAbortLikeError(error)) {
          return;
        }
        if (
          !cancelled &&
          lessonIdRef.current === lessonId &&
          loadAttemptRef.current === attemptWhenStarted
        ) {
          setSession((prev) => ({
            ...prev,
            isInitializing: false,
            initError: getErrorMessage(error),
          }));
        }
      }
    }

    void initialize();
    return () => {
      cancelled = true;
      abortController.abort();
    };
  }, [lessonId, session.loadAttempt]);

  const openLeaveDialog = useCallback(() => {
    setSession((prev) => ({ ...prev, isLeaveDialogOpen: true }));
  }, []);

  const closeLeaveDialog = useCallback(() => {
    setSession((prev) => ({ ...prev, isLeaveDialogOpen: false }));
  }, []);

  const retryInitLoad = useCallback(() => {
    setSession((prev) => ({ ...prev, loadAttempt: prev.loadAttempt + 1 }));
  }, []);

  const handleCheck = useCallback(async () => {
    if (!currentItem || !selectedOptionId || submitMutation.isPending) {
      return;
    }
    try {
      const result = await submitMutation.mutateAsync([
        { itemId: currentItem.item_id, optionId: selectedOptionId },
      ]);
      if (lessonIdRef.current !== lessonId) {
        return;
      }
      const itemResult = result.item_results[0];
      if (!itemResult) {
        return;
      }
      const feedback: FeedbackState = {
        expectedAnswer: optionChar(currentItem, itemResult.expected_option_id),
        submittedAnswer: optionChar(currentItem, itemResult.user_option_id),
        isCorrect: itemResult.is_correct,
      };
      if (itemResult.is_correct) {
        setSession((prev) => ({
          ...prev,
          feedback,
          correctCount: prev.correctCount + 1,
          finalAnswers: {
            ...prev.finalAnswers,
            [currentItem.item_id]: itemResult.expected_option_id,
          },
          completedItemIds: prev.completedItemIds.includes(currentItem.item_id)
            ? prev.completedItemIds
            : [...prev.completedItemIds, currentItem.item_id],
        }));
        return;
      }
      setSession((prev) => ({
        ...prev,
        feedback,
        mistakeCount: prev.mistakeCount + 1,
        reviewQueue: [...prev.reviewQueue, { itemId: currentItem.item_id, source: "review" }],
      }));
    } catch {
      // mutation error surfaced in returned state
    }
  }, [currentItem, lessonId, selectedOptionId, submitMutation]);

  const advanceQueue = useCallback(async () => {
    if (session.feedback === null) {
      return;
    }
    setSelectedOptionId(null);
    setSession((prev) => ({ ...prev, continueError: null }));

    if (hasMoreMainItemsToLoad(session.totalItems, session.nextCursorToLoad)) {
      nextMainItemLoadAbortRef.current?.abort();
      const ac = new AbortController();
      nextMainItemLoadAbortRef.current = ac;
      setIsNextMainItemPending(true);
      try {
        const nextItem = await loadKanaLessonItem(lessonId, session.nextCursorToLoad, ac.signal);
        if (lessonIdRef.current !== lessonId) {
          return;
        }
        setSession((prev) => ({
          ...prev,
          feedback: null,
          itemCache: { ...prev.itemCache, [nextItem.item_id]: nextItem },
          currentQueueEntry: { itemId: nextItem.item_id, source: "main" },
          nextCursorToLoad: prev.nextCursorToLoad + 1,
        }));
      } catch (error) {
        if (!isAbortLikeError(error)) {
          setSession((prev) => ({ ...prev, continueError: getErrorMessage(error) }));
        }
      } finally {
        setIsNextMainItemPending(false);
      }
      return;
    }

    if (session.reviewQueue.length > 0) {
      setSession((prev) => {
        const [nextReview, ...remaining] = prev.reviewQueue;
        if (!nextReview) {
          return prev;
        }
        return {
          ...prev,
          feedback: null,
          reviewQueue: remaining,
          currentQueueEntry: nextReview,
        };
      });
      return;
    }

    const answers = orderedCompletionAnswers(session.itemCache, session.finalAnswers);
    if (!answers) {
      setSession((prev) => ({
        ...prev,
        continueError: "Could not finish the lesson: some answers are missing.",
      }));
      return;
    }

    try {
      const result = await submitMutation.mutateAsync(answers);
      if (lessonIdRef.current !== lessonId) {
        return;
      }
      setSession((prev) => ({
        ...prev,
        feedback: null,
        isLessonFinished: true,
        completionProgressState: result.progress_state,
        currentQueueEntry: null,
      }));
      void refreshKanaOverviewQuery(queryClient);
    } catch (error) {
      setSession((prev) => ({ ...prev, continueError: getErrorMessage(error) }));
    }
  }, [
    lessonId,
    queryClient,
    session.feedback,
    session.finalAnswers,
    session.itemCache,
    session.nextCursorToLoad,
    session.reviewQueue.length,
    session.totalItems,
    submitMutation,
  ]);

  const totalCount = lessonTotalCount(session.totalItems, currentItem?.total_items);
  const currentIndex = lessonCurrentIndex(session.completedItemIds.length, totalCount);
  const progressBarFillCompletedCount = useMemo(() => {
    if (session.isLessonFinished) {
      return totalCount;
    }
    return topBarCompletedItemCount({ currentIndex, totalCount });
  }, [currentIndex, session.isLessonFinished, totalCount]);

  const canCheckComputed =
    selectedOptionId !== null && session.feedback === null && !submitMutation.isPending;

  useLessonSpaceShortcut({
    advanceQueue,
    blockProgress: submitMutation.isPending || isNextMainItemPending,
    canCheck: canCheckComputed,
    feedback: session.feedback,
    handleCheck,
    isLeaveDialogOpen: session.isLeaveDialogOpen,
    isLessonFinished: session.isLessonFinished,
  });

  return {
    currentItem,
    selectedOptionId,
    selectOption: setSelectedOptionId,
    feedback: session.feedback,
    correctCount: session.correctCount,
    mistakeCount: session.mistakeCount,
    isLessonFinished: session.isLessonFinished,
    completionProgressState: session.completionProgressState,
    isInitializing: session.isInitializing,
    initError: session.initError,
    isLeaveDialogOpen: session.isLeaveDialogOpen,
    openLeaveDialog,
    closeLeaveDialog,
    retryInitLoad,
    canCheck: canCheckComputed,
    totalCount,
    currentIndex,
    progressBarFillCompletedCount,
    remainingReviewCount: remainingReviewCountModel(
      session.reviewQueue.length,
      session.currentQueueEntry?.source ?? null,
    ),
    checkAnswerError:
      submitMutation.error && session.feedback === null
        ? getErrorMessage(submitMutation.error)
        : null,
    continueFooterError: session.continueError,
    continuePending: isNextMainItemPending || submitMutation.isPending,
    isCheckAnswerPending: submitMutation.isPending && session.feedback === null,
    advanceQueue,
    handleCheck,
  };
}
